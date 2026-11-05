import sharp from 'sharp';
import fs from 'node:fs/promises';
const root='D:/Nhom8_LapTrinhMang/.presentation-build/demo-v2/';
const boxes={devices:{left:0,top:0,width:1392,height:270},alerts:{left:0,top:0,width:1392,height:220}};
for(const name of ['devices','alerts','rtt','dialog']){
  let image=sharp(root+name+'.png');
  const meta=await image.metadata();
  const box=boxes[name];
  if(box)image=image.extract({...box,width:Math.min(box.width,meta.width),height:Math.min(box.height,meta.height)});
  await image.jpeg({quality:84,mozjpeg:true}).toFile(root+name+'.jpg');
  console.log(name+': '+(await fs.stat(root+name+'.jpg')).size+' bytes');
}
