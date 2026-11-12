import * as taskPaths from 'node:path';
import {fileURLToPath as taskFileURLToPath} from 'node:url';
import sharp from 'sharp';
import fs from 'node:fs/promises';
const root=taskPaths.resolve(taskPaths.dirname(taskFileURLToPath(import.meta.url)), '../../.presentation-build/demo-v2') + taskPaths.sep;
const boxes={devices:{left:0,top:0,width:1392,height:270},alerts:{left:0,top:0,width:1392,height:220}};
for(const name of ['devices','alerts','rtt','dialog']){
  let image=sharp(root+name+'.png');
  const meta=await image.metadata();
  const box=boxes[name];
  if(box)image=image.extract({...box,width:Math.min(box.width,meta.width),height:Math.min(box.height,meta.height)});
  await image.jpeg({quality:84,mozjpeg:true}).toFile(root+name+'.jpg');
  console.log(name+': '+(await fs.stat(root+name+'.jpg')).size+' bytes');
}
