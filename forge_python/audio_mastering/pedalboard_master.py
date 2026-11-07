"""Master a music stem and voiceover into a cinematic stereo WAV."""
import argparse
import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from pedalboard import Pedalboard, LowpassFilter, Chorus, Reverb, Limiter
from scipy.signal import resample_poly
from scipy.ndimage import minimum_filter1d, gaussian_filter1d


def duck_envelope(voice, sample_rate, threshold_db=-45):
    """Smoothed gain in linear units, 40 ms attack and 250 ms release."""
    level = np.max(np.abs(voice), axis=1)
    active = level > 10 ** (threshold_db / 20)
    target_duck = 10 ** (-5.5 / 20)
    attack = np.exp(-1 / (0.040 * sample_rate))
    release = np.exp(-1 / (0.250 * sample_rate))
    result = np.empty(len(level), dtype=np.float32)
    gain = 1.0
    for i, on in enumerate(active):
        target = target_duck if on else 1.0
        coefficient = attack if on else release
        gain = target + coefficient * (gain - target)
        result[i] = gain
    return result

def stereo(samples):
    if samples.ndim == 1: samples = samples[:, None]
    if samples.shape[1] == 1: return np.repeat(samples, 2, axis=1)
    if samples.shape[1] != 2: raise ValueError('only mono or stereo stems supported')
    return samples

def constrain_oversampled_peak(audio, sample_rate, ceiling_db=-1.0):
    """Lookahead reduction followed by a verified 4x polyphase peak correction.

    This checks this particular 4x reconstruction, not a certified BS.1770
    measurement or the output of a subsequent lossy encoder.
    """
    audio=np.asarray(audio, dtype=np.float64)
    if not np.all(np.isfinite(audio)): raise ValueError('audio contains non-finite samples')
    limit=10**(ceiling_db/20) * 0.99999
    oversampled=resample_poly(audio,4,1,axis=0)
    peaks=np.max(np.abs(oversampled).reshape(len(audio),4,-1),axis=(1,2))
    desired=np.minimum(1., limit/np.maximum(peaks,1e-20))
    window=max(3, int(sample_rate*.010) | 1)
    anticipated=minimum_filter1d(desired,size=window,mode='nearest')
    smooth=gaussian_filter1d(anticipated,sigma=max(1,sample_rate*.001),mode='nearest')
    envelope=np.minimum(anticipated,smooth)
    out=audio * envelope[:,None]
    # Multiplication itself changes intersample reconstruction, so remeasure.
    peak=float(np.max(np.abs(resample_poly(out,4,1,axis=0))))
    if peak>limit: out*=limit/peak
    return out.astype(np.float32)

def master(music, voice, sample_rate, seed=0, sfx=None, voice_presence=False):
    music, voice = stereo(np.asarray(music, dtype=np.float32)), stereo(np.asarray(voice, dtype=np.float32))
    if voice_presence:
        from scipy.signal import iirpeak, lfilter
        b,a=iirpeak(3000,1.0,fs=sample_rate)
        voice=voice+(10**(1.5/20)-1)*lfilter(b,a,voice,axis=0)
    if sfx is not None: sfx=stereo(np.asarray(sfx,dtype=np.float32))
    length = max(len(music), len(voice),len(sfx) if sfx is not None else 0)
    if length == 0: raise ValueError('stems must not both be empty')
    music = np.pad(music, ((0, length-len(music)), (0, 0)))
    voice = np.pad(voice, ((0, length-len(voice)), (0, 0)))
    board = Pedalboard([LowpassFilter(cutoff_frequency_hz=min(10000, sample_rate * .45)), Chorus(), Reverb(room_size=0.82, wet_level=0.45)])
    processed = board(music.T, sample_rate).T
    # Low-pass filtered noise provides a deterministic, dark room-tone bed at -38 dB RMS.
    from scipy.signal import lfilter
    noise = np.random.default_rng(seed).standard_normal((length, 2))
    noise = lfilter([0.03], [1, -0.97], noise, axis=0)
    rms = np.sqrt(np.mean(noise ** 2))
    if rms: noise *= 10 ** (-38 / 20) / rms
    mix = (processed + noise) * duck_envelope(voice, sample_rate)[:, None] + voice
    if sfx is not None: mix+=np.pad(sfx,((0,length-len(sfx)),(0,0)))
    meter = pyln.Meter(sample_rate)
    if length < int(0.4 * sample_rate): raise ValueError('audio must be at least 0.4 seconds for LUFS measurement')
    loudness = meter.integrated_loudness(mix)
    if not np.isfinite(loudness): raise ValueError('mix is too quiet to measure')
    # Apply loudness gain directly: intermediate peaks may exceed full scale,
    # but the float master bus below handles them without clipping or warnings.
    mix *= 10 ** ((-13.5 - loudness) / 20)
    limiter = Pedalboard([Limiter(threshold_db=-1.2, release_ms=60.0)])
    mix = limiter(mix.astype(np.float32).T, sample_rate).T
    # Correct limiter gain toward the final integrated target.
    measured = meter.integrated_loudness(mix)
    if np.isfinite(measured): mix *= 10 ** ((-14.0 - measured) / 20)
    # A peak ceiling and exact loudness can be incompatible. Preserve the ceiling.
    return constrain_oversampled_peak(mix, sample_rate)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('music'); parser.add_argument('voice'); parser.add_argument('output'); parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()
    music, sr = sf.read(args.music, always_2d=True, dtype='float32')
    voice, voice_sr = sf.read(args.voice, always_2d=True, dtype='float32')
    if sr != voice_sr: parser.error('stems must have the same sample rate')
    mix = master(music, voice, sr, args.seed)
    # Float avoids silently clipping peaks after loudness normalization.
    sf.write(args.output, mix, sr, subtype='FLOAT')
    loudness = pyln.Meter(sr).integrated_loudness(mix)
    print(f'Mastered integrated loudness: {loudness:.2f} LUFS (target -14 ± 0.5)')
    if not -14.5 <= loudness <= -13.5: print('Warning: peak ceiling prevented the loudness target; adjust the source mix.')
if __name__ == '__main__': main()
