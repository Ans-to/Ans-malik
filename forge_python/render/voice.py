"""Offline espeak-ng speech and engine-reported word events."""
import ctypes as C
from pathlib import Path
import re
import numpy as np
from scipy.signal import resample_poly
import espeakng_loader

class EventId(C.Union):
    _fields_=[('number',C.c_int),('name',C.c_char_p),('string',C.c_char*8)]
class Event(C.Structure):
    _fields_=[('type',C.c_int),('unique_identifier',C.c_uint),('text_position',C.c_int),('length',C.c_int),('audio_position',C.c_int),('sample',C.c_int),('user_data',C.c_void_p),('id',EventId)]
Callback=C.CFUNCTYPE(C.c_int,C.POINTER(C.c_short),C.c_int,C.POINTER(Event))

class OfflineVoice:
    def __init__(self):
        self.lib=espeakng_loader.load_library()
        lib=self.lib
        lib.espeak_Initialize.argtypes=[C.c_int,C.c_int,C.c_char_p,C.c_int]; lib.espeak_Initialize.restype=C.c_int
        self.rate=lib.espeak_Initialize(2,0,str(Path(espeakng_loader.get_data_path()).parent).encode(),0)
        if self.rate <= 0: raise RuntimeError('espeak-ng initialization failed')
        lib.espeak_SetVoiceByName.argtypes=[C.c_char_p]; lib.espeak_SetVoiceByName(b'en-us')
        lib.espeak_SetParameter.argtypes=[C.c_int,C.c_int,C.c_int]
        if lib.espeak_SetParameter(1,145,0)!=0: raise RuntimeError('could not set offline narration rate')
        lib.espeak_SetSynthCallback.argtypes=[Callback]
        lib.espeak_Synth.argtypes=[C.c_void_p,C.c_size_t,C.c_uint,C.c_int,C.c_uint,C.c_uint,C.c_void_p,C.c_void_p]
        self.chunks=[]; self.events=[]
        @Callback
        def callback(wav, count, events):
            if wav and count: self.chunks.append(np.ctypeslib.as_array(wav,shape=(count,)).copy())
            if events:
                i=0
                while events[i].type:
                    event=events[i]
                    if event.type==1: self.events.append((event.text_position,event.length,event.audio_position))
                    i+=1
            return 0
        self.callback=callback; lib.espeak_SetSynthCallback(callback)

    def speak(self,text,output_rate=24000):
        self.chunks=[]; self.events=[]
        raw=text.encode('utf-8'); buf=C.create_string_buffer(raw+b'\0')
        if self.lib.espeak_Synth(buf,len(raw)+1,0,1,0,1,None,None)!=0: raise RuntimeError('espeak synthesis failed')
        if not self.chunks: raise RuntimeError('espeak generated no samples')
        audio=np.concatenate(self.chunks).astype(np.float32)/32768
        words=[]
        for position,length,ms in self.events:
            word=raw[max(0,position-1):max(0,position-1)+length].decode('utf-8',errors='replace').strip()
            if word: words.append({'word':word,'start_ms':ms})
        for i,item in enumerate(words): item['end_ms']=words[i+1]['start_ms'] if i+1<len(words) else round(len(audio)/self.rate*1000)
        if output_rate!=self.rate: audio=resample_poly(audio,output_rate,self.rate).astype(np.float32)
        return audio,words
