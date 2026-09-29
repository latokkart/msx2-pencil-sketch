import re, json, numpy as np, sys
L=open(sys.argv[1] if len(sys.argv)>1 else 'intro_timing.log').read().splitlines()
F=[]
for l in L:
    m=re.match(r'F idx=(\d+) t=([\d.]+) r23=(\d+) r1=(\d+) pal=(.*)',l)
    if m:
        p=[int(x)&255 for x in m.group(5).split()]
        top=(p[4]>>4, p[5]&7, p[4]&7)      # index 15: r,g,b
        F.append((int(m.group(1)),float(m.group(2)),int(m.group(3)),int(m.group(4)),top,p))
t=np.array([f[1] for f in F]); lvl=np.array([sum(f[4]) for f in F])   # r+g+b (0..21)
full=lvl==21; nz=lvl>0
i_first_nz=np.argmax(nz); i_full0=np.argmax(full); i_full1=len(full)-1-np.argmax(full[::-1])
i_last_nz=len(nz)-1-np.argmax(nz[::-1])
dt=np.diff(t[1:])
print('frame period after first: mean %.6f ms min %.3f max %.3f'%(dt.mean()*1e3,dt.min()*1e3,dt.max()*1e3))
print('R#23 values during intro:',sorted(set(f[2] for f in F)),' R#1:',sorted(set(f[3] for f in F)))
# visible changes take effect from the frame after the ISR that wrote them: use ISR times as frame boundaries
fade_in=t[i_full0]-t[i_first_nz]; hold=t[i_full1+1]-t[i_full0]; fade_out=t[i_last_nz+1]-t[i_full1+1]
print('black lead: display on/first ISR %.3f -> first non-black %.3f = %.3f s'%(t[0],t[i_first_nz],t[i_first_nz]-t[0]))
print('fade-in : %.4f s (%d frames) first non-black idx %d -> first full idx %d'%(fade_in,i_full0-i_first_nz,F[i_first_nz][0],F[i_full0][0]))
print('hold    : %.4f s (%d frames at full white)'%(hold,i_full1+1-i_full0))
print('fade-out: %.4f s (%d frames) until all-black'%(fade_out,i_last_nz+1-(i_full1+1)))
steps_in=sorted(set(lvl[i_first_nz:i_full0+1])); steps_out=sorted(set(lvl[i_full1:i_last_nz+2]))
print('distinct fade-in levels (r+g+b of idx15):',len(steps_in),steps_in)
print('distinct fade-out levels:',len(steps_out))
em=[l for l in L if l.startswith('ENGINE')][0]; te=float(re.search(r't=([\d.]+)',em).group(1))
print('last intro ISR %.3f, engine first ISR %.3f (black gap incl. VRAM clear %.3f s after fade-out end %.3f)'%(t[-1],te,te-t[i_last_nz+1],t[i_last_nz+1]))
print('intro enter', [l for l in L if l.startswith('INTRO_ENTER')][0])
