'use client';
import { Canvas, useFrame } from '@react-three/fiber';
import { useRef } from 'react';
import * as THREE from 'three';

function Character({speaking}: {speaking:boolean}) {
  const group = useRef<THREE.Group>(null);
  const mouth = useRef<THREE.Mesh>(null);
  useFrame(({clock})=>{
    if(group.current) { group.current.position.y = Math.sin(clock.elapsedTime*1.7)*.08; group.current.rotation.y = Math.sin(clock.elapsedTime*.6)*.17; }
    if(mouth.current) mouth.current.scale.y = speaking ? .5+Math.abs(Math.sin(clock.elapsedTime*15))*2 : .35;
  });
  return <group ref={group}>
    <mesh><sphereGeometry args={[1,48,48]}/><meshStandardMaterial color="#ff6b16" roughness={.24} metalness={.12}/></mesh>
    {[-.34,.34].map(x=><group key={x} position={[x,.15,.9]}><mesh><sphereGeometry args={[.18,24,24]}/><meshStandardMaterial color="#fff9ef"/></mesh><mesh position={[.03,0,.16]}><sphereGeometry args={[.075,20,20]}/><meshStandardMaterial color="#242031"/></mesh></group>)}
    <mesh ref={mouth} position={[0,-.35,.94]}><sphereGeometry args={[.19,24,24]}/><meshStandardMaterial color="#5c231b"/></mesh>
    <mesh position={[0,1.06,0]} rotation={[0,0,-.2]}><capsuleGeometry args={[.11,.3,8,16]}/><meshStandardMaterial color="#7fbd74"/></mesh>
    {[-1,1].map(x=><mesh key={x} position={[x*.99,-.2,0]} rotation={[0,0,x*.7]}><capsuleGeometry args={[.13,.4,8,16]}/><meshStandardMaterial color="#ff6b16"/></mesh>)}
  </group>;
}
export default function Mascot({speaking}: {speaking:boolean}) {
  return <Canvas camera={{position:[0,.2,4.3]}} aria-label="Animated Swiggy analytics mascot"><ambientLight intensity={1.7}/><directionalLight position={[3,4,4]} intensity={3}/><Character speaking={speaking}/></Canvas>;
}
