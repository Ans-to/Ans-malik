// Continuous piecewise-linear mapping from audio seconds to authored timeline seconds.
export function warpTime(t, marks){
 if(t<=marks[0].real)return marks[0].virtual;
 for(let i=0;i<marks.length-1;i++){const a=marks[i],b=marks[i+1];if(t<=b.real)return a.virtual+(t-a.real)/(b.real-a.real)*(b.virtual-a.virtual)}
 return marks.at(-1).virtual;
}
