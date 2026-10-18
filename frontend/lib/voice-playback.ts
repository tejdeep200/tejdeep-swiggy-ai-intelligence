type DeviceVoice = {name: string; lang: string};

export function preferredFemaleVoice<T extends DeviceVoice>(voices: T[]): T | undefined {
  const female = /neerja|jenny|aria|sonia|natasha|michelle|sara|libby|samantha|karen|tessa|moira|fiona|zira|hazel|female|google us english/i;
  return voices.filter(v=>v.lang.toLowerCase().startsWith('en') && female.test(v.name))
    .sort((a,b)=>Number(/natural|neural|online/i.test(b.name))-Number(/natural|neural|online/i.test(a.name)))[0];
}

export function speechSummary(text: string): string {
  const clean=text.replace(/RAG coverage:[\s\S]*$/i,'').replace(/[*#`]/g,'').replace(/\s+/g,' ').trim();
  if(clean.length<=200) return clean;
  const prefix=clean.slice(0,197);
  return prefix.slice(0,prefix.lastIndexOf(' '))+ '…';
}

type Callbacks={speaking:(value:boolean)=>void;loading:(value:boolean)=>void;notice:(message:string)=>void};
type Platform={
  fetch: typeof fetch;
  synth: SpeechSynthesis;
  audio: (url:string)=>HTMLAudioElement;
  utterance: (text:string)=>SpeechSynthesisUtterance;
  createURL: (blob:Blob)=>string;
  revokeURL: (url:string)=>void;
};

export class VoicePlayback {
  private generation=0;
  private deadline:ReturnType<typeof setTimeout>|null=null;
  private request:AbortController|null=null;
  private player:HTMLAudioElement|null=null;
  private url:string|null=null;
  private callbacks:Callbacks;
  private platform:Platform;
  constructor(callbacks:Callbacks, platform:Platform) {this.callbacks=callbacks;this.platform=platform;}

  stop() {
    this.generation++;
    if(this.deadline!==null){clearTimeout(this.deadline);this.deadline=null;}
    this.request?.abort();this.request=null;
    if(this.player){this.player.onended=null;this.player.onerror=null;this.player.pause();this.player.removeAttribute('src');this.player=null;}
    if(this.url){this.platform.revokeURL(this.url);this.url=null;}
    this.platform.synth?.cancel();
    this.callbacks.speaking(false);this.callbacks.loading(false);
  }

  private speakDevice(summary:string, voice:DeviceVoice, generation:number) {
    this.callbacks.loading(false);
    this.callbacks.notice(`${voice.name} - female voice. Stop voice keeps your charts visible.`);
    const utterance=this.platform.utterance(summary);utterance.voice=voice as SpeechSynthesisVoice;
    utterance.rate=.95;utterance.pitch=1;
    utterance.onstart=()=>{if(generation===this.generation)this.callbacks.speaking(true);};
    utterance.onend=utterance.onerror=()=>{if(generation===this.generation)this.callbacks.speaking(false);};
    this.platform.synth.speak(utterance);
  }

  async speak(text:string) {
    this.stop();const generation=this.generation;
    const summary=speechSummary(text);if(!summary)return;
    const deviceVoice=preferredFemaleVoice(this.platform.synth?.getVoices()||[]);
    if(deviceVoice && /natural|neural|online/i.test(deviceVoice.name)) {
      this.speakDevice(summary,deviceVoice,generation);return;
    }
    this.request=new AbortController();this.callbacks.loading(true);this.callbacks.notice('');
    try {
      const pending=this.platform.fetch('/api/speech',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:summary}),signal:this.request.signal}).then(async response=>({response,blob:response.ok?await response.blob():null}));
      // Include body download in the deadline, not just response headers.
      const loaded=deviceVoice ? await Promise.race([pending,new Promise<never>((_resolve,reject)=>{
        this.deadline=setTimeout(()=>{this.request?.abort();reject(new Error('Using a faster female device voice.'));},1500);
      })]) : await pending;
      if(generation!==this.generation)return;
      if(this.deadline!==null){clearTimeout(this.deadline);this.deadline=null;}
      const {response,blob}=loaded;
      if(!response.ok){const data=await response.json();throw new Error(data.detail?.message||'Natural voice unavailable. Using a device voice.');}
      const name=response.headers.get('x-voice-name');
      if(name)this.callbacks.notice(`${name} · natural female voice. Stop voice keeps your charts visible.`);
      if(!blob)return;
      this.url=this.platform.createURL(blob);const audio=this.platform.audio(this.url);this.player=audio;
      audio.onended=()=>{if(generation===this.generation)this.stop();};
      audio.onerror=()=>{if(generation===this.generation){this.stop();this.callbacks.notice('Audio could not play. Tap Play summary to try again.');}};
      await audio.play();if(generation!==this.generation)return;
      this.callbacks.loading(false);this.callbacks.speaking(true);
    } catch(error:any) {
      if(generation!==this.generation)return;
      if(this.deadline!==null){clearTimeout(this.deadline);this.deadline=null;}
      this.callbacks.loading(false);
      if(error?.name==='NotAllowedError'){this.stop();this.callbacks.notice('Tap Play summary to allow audio playback.');return;}
      const voice=preferredFemaleVoice(this.platform.synth?.getVoices()||[]);
      this.callbacks.notice(error?.message||'Natural voice unavailable.');
      if(!voice){this.callbacks.notice((error?.message||'Natural voice unavailable.')+' No female device voice is installed. Charts remain available.');return;}
      this.speakDevice(summary,voice,generation);
    }
  }
}
