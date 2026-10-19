import assert from 'node:assert/strict';
import test from 'node:test';
import { VoicePlayback, preferredFemaleVoice, speechSummary } from '../lib/voice-playback.ts';

function fixture(fetch) {
  const state={speaking:false,loading:false,notice:'',played:0,paused:0,revoked:0,utterance:null};
  const player={play:async()=>{state.played++},pause:()=>{state.paused++},removeAttribute:()=>{}};
  const platform={fetch,synth:{cancel:()=>{},getVoices:()=>[{name:'Microsoft Zira',lang:'en-US'}],speak:u=>{state.utterance=u}},audio:()=>player,utterance:text=>({text}),createURL:()=> 'blob:voice',revokeURL:()=>{state.revoked++}};
  const voice=new VoicePlayback({speaking:v=>{state.speaking=v},loading:v=>{state.loading=v},notice:v=>{state.notice=v}},platform);
  return {voice,state,platform};
}

test('prefers a natural female voice over default male and older device voices',()=>{
  const voices=[{name:'Microsoft David',lang:'en-US'},{name:'Microsoft Zira',lang:'en-US'},{name:'Microsoft Neerja Online (Natural)',lang:'en-IN'}];
  assert.equal(preferredFemaleVoice(voices)?.name,voices[2].name);
  assert.equal(preferredFemaleVoice([voices[0]]),undefined);
});

test('spoken summaries omit technical coverage and stay within the TTS limit',()=>{
  assert.equal(speechSummary('**Hello!** RAG coverage: 20 listings.'),'Hello!');
  assert.ok(speechSummary('Restaurant insights. '.repeat(30)).length<=200);
});

test('Stop cancels a pending voice request and a late response cannot start audio',async()=>{
  let resolve;let signal;
  const {voice,state}=fixture((_url,options)=>{signal=options.signal;return new Promise(r=>{resolve=r})});
  const pending=voice.speak('Hi!');voice.stop();
  assert.equal(signal.aborted,true);
  resolve(new Response(new Blob(['RIFFaudio'])));await pending;
  assert.equal(state.played,0);assert.equal(state.loading,false);assert.equal(state.speaking,false);
});

test('Stop pauses active audio and releases its URL',async()=>{
  const {voice,state}=fixture(async()=>new Response(new Blob(['RIFFaudio'])));
  await voice.speak('Hi!');assert.equal(state.speaking,true);
  voice.stop();assert.equal(state.paused,1);assert.equal(state.revoked,1);assert.equal(state.speaking,false);
});

test('an unavailable natural voice falls back to an available female device voice',async()=>{
  const {voice,state}=fixture(async()=>Response.json({detail:{message:'Natural voice needs terms acceptance.'}},{status:503}));
  await voice.speak('Hi!');assert.equal(state.utterance.voice.name,'Microsoft Zira');assert.equal(state.utterance.rate,.95);
});


test('a natural female browser voice starts without a server request',async()=>{
  let requests=0;
  const {voice,state,platform}=fixture(async()=>{requests++;throw new Error('should not fetch')});
  platform.synth.getVoices=()=>[{name:'Microsoft Jenny Online (Natural)',lang:'en-US'}];
  await voice.speak('Hi!');
  assert.equal(requests,0);assert.equal(state.utterance.voice.name,'Microsoft Jenny Online (Natural)');
  assert.equal(state.loading,false);
});

test('slow server audio falls back within 1.5 seconds and never plays late',async(t)=>{
  t.mock.timers.enable({apis:['setTimeout']});
  let resolve,signal;
  const {voice,state}=fixture((_url,options)=>{signal=options.signal;return new Promise(r=>{resolve=r})});
  const pending=voice.speak('Hi!');
  t.mock.timers.tick(1500);await pending;
  assert.equal(signal.aborted,true);assert.equal(state.utterance.voice.name,'Microsoft Zira');
  resolve(new Response(new Blob(['RIFFaudio'])));await Promise.resolve();
  assert.equal(state.played,0);assert.equal(state.loading,false);
});

test('Stop prevents the latency deadline from starting fallback speech',async(t)=>{
  t.mock.timers.enable({apis:['setTimeout']});
  let resolve;
  const {voice,state}=fixture(()=>new Promise(r=>{resolve=r}));
  const pending=voice.speak('Hi!');voice.stop();t.mock.timers.tick(2000);
  resolve(new Response(new Blob(['RIFFaudio'])));await pending;
  assert.equal(state.utterance,null);assert.equal(state.played,0);
});


test('an explicit chart narration restarts after Stop without waiting for the server',async()=>{
 let requests=0;
 const {voice,state}=fixture(async()=>{requests++;throw new Error('must not fetch')});
 voice.stop();await voice.speak('Average rating. Mumbai: 4.5, highest shown.',true);
 assert.equal(requests,0);assert.match(state.utterance.text,/Mumbai: 4.5/);
 assert.equal(state.utterance.voice.name,'Microsoft Zira');
});
