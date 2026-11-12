import * as taskPaths from 'node:path';
import {fileURLToPath as taskFileURLToPath} from 'node:url';
const C={ink:'#17243B',blue:'#2563EB',muted:'#52637B',surface:'#EAF1FF'};
function text(s,value,x,y,w,h,size=28,color=C.ink,bold=false){
 const a=s.shapes.add({geometry:'textbox',name:value.slice(0,55),position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 a.text=value;a.text.style={typeface:'Arial',fontSize:size,color,bold,verticalAlignment:'top',insets:0,autoFit:'none',wrap:'square'};return a;
}
function pic(s,src,alt,x,y,w,h){return s.images.add({dataUrl:src,alt,fit:'contain',position:{left:x,top:y,width:w,height:h}});}
async function clearBody(p,index){
 const result=await p.inspect({select:`$.slides[${index}].elements[*]`,include:['id','kind','text']});
 p.delete(result.records.slice(2).map(e=>e.id));
 return p.slides.items[index];
}
export async function edit(p,assets){
 const footers=await p.inspect({kind:'textbox',search:'NetGuard · Nhóm 8',maxChars:100000});
 p.delete(footers.records.filter(r=>r.text==='NetGuard · Nhóm 8').map(r=>r.id));
 let s=await clearBody(p,2);
 text(s,'Theo dõi thiết bị và kết nối',72,166,550,54,33,C.blue,true);
 text(s,'IP, MAC và trạng thái quan sát\nTên, ghi chú và mức tin cậy\nCảnh báo thiết bị mới\nRTT, mất gói và lịch sử',72,253,550,210,29);
 text(s,'Đặt tên và ghi chú',690,166,510,54,33,C.blue,true);
 pic(s,assets.dialog,'Hộp thoại thật của NetGuard với tên và ghi chú từ dữ liệu mô phỏng',690,246,510,247);
 text(s,'Hộp thoại với dữ liệu mô phỏng',690,512,510,46,23,C.muted);
 text(s,'Phạm vi chính: mạng LAN IPv4 trên Windows',72,574,1128,52,30,C.ink,true);
 text(s,'Ứng dụng giám sát và cảnh báo, không ngắt kết nối thiết bị.',72,628,1128,32,23,C.muted);
 s.speakerNotes.text+='\n\nẢnh bổ sung: giao diện DeviceDialog thật, kết xuất với dữ liệu mẫu trong bộ nhớ bằng .presentation-build/render_demo_v2.py. Không gửi gói mạng hay ghi cơ sở dữ liệu sử dụng thật.';

 s=await clearBody(p,4);
 text(s,'Quét subnet của card mạng đã chọn',72,158,1128,48,33,C.blue,true);
 text(s,'Gửi ARP Request, thu ARP Reply để ghi nhận IP và MAC.',72,216,1128,47,28);
 text(s,'Ví dụ danh sách thiết bị sau quét (dữ liệu mô phỏng)',72,273,1128,37,23,C.muted);
 pic(s,assets.devices,'Bảng thiết bị của giao diện NetGuard với dữ liệu mô phỏng gồm router, laptop, điện thoại và thiết bị chưa tin cậy',72,321,1136,220);
 text(s,'30 giây',72,562,470,57,43,C.blue,true);
 text(s,'Chu kỳ quét cấu hình',72,621,550,34,24,C.muted);
 text(s,'3 lần quét liên tiếp',690,562,510,57,38,C.blue,true);
 text(s,'Vắng mặt mới xác nhận offline',690,621,510,34,24,C.muted);
 s.speakerNotes.text+='\n\nẢnh bổ sung: bảng thiết bị từ MainWindow thật, dữ liệu mô phỏng để minh họa các trường IP/MAC, Online và cờ tin cậy. Ảnh không phải kết quả quét mạng thật. Thiết bị ngủ hoặc client isolation có thể làm thiếu phản hồi. Quét lỗi không tính là vắng mặt.';

 s=await clearBody(p,5);
 for(const [n,value,y] of [[1,'Thu thập danh sách thiết bị ban đầu',161],[2,'Chốt baseline để bắt đầu theo dõi thiết bị mới',218],[3,'Cảnh báo thiết bị mới chưa tin cậy',275],[4,'Người dùng kiểm tra và xác nhận',332]]){
  text(s,String(n).padStart(2,'0'),72,y,65,43,29,C.blue,true);
  text(s,value,160,y,1040,43,29,C.ink,true);
 }
 text(s,'Ví dụ cảnh báo từ giao diện (dữ liệu mô phỏng)',72,390,1136,34,23,C.muted);
 pic(s,assets.alerts,'Tab Cảnh báo thật của NetGuard hiển thị cảnh báo thiết bị mới 192.168.1.25, dùng dữ liệu mô phỏng',72,434,1136,180);
 text(s,'Baseline hiện chốt qua CLI. “Tin cậy tất cả” chỉ cập nhật mức tin cậy.',72,633,1130,31,21,C.muted);
 s.speakerNotes.text+='\n\nẢnh bổ sung: cảnh báo tạo bằng services.alerts.make_stranger_alert với Device mô phỏng trong bộ nhớ, hiển thị trên tab Cảnh báo thật. Không có thiết bị lạ được kết nối hay cảnh báo mạng thật được tạo trong lần chuẩn bị này.';

 s=await clearBody(p,8);
 text(s,'Demo thiết bị mới',72,158,548,52,33,C.blue,true);
 text(s,'Quét danh sách ban đầu\nChốt baseline rồi thêm thiết bị\nXem cảnh báo, cập nhật tin cậy',72,232,548,155,28);
 text(s,'Demo khôi phục LAN',690,158,510,52,33,C.blue,true);
 text(s,'Tắt Wi-Fi trên máy chạy ứng dụng\nQuan sát trạng thái mất LAN\nBật lại và theo dõi phép đo tiếp tục',690,232,510,155,27);
 pic(s,assets.rtt,'Đồ thị RTT thật của giao diện NetGuard hiển thị ba chuỗi dữ liệu mô phỏng, không phải số đo mạng thực tế',72,425,1136,132);
 text(s,'RTT mô phỏng: router (xanh dương), ISP (cam), Internet (xanh lá)',72,579,1136,52,24,C.muted);
 text(s,'Chuẩn bị: Npcap, quyền Admin, mạng không cô lập client và thiết bị chưa có trong dữ liệu demo.',72,634,1136,31,20,C.muted);
 s.speakerNotes.text+='\n\nẢnh đồ thị: PlotWidget thật của tab Chẩn đoán. Các mẫu ping được tạo trong bộ nhớ để minh họa cách vẽ ba chuỗi RTT. Dữ liệu mô phỏng không đánh giá hiệu năng mạng hay chứng minh khả năng khoanh vùng lỗi ngoài thực tế.';

 for(let i=1;i<11;i++){
  const slide=p.slides.items[i];
  const panel=slide.shapes.add({geometry:'rect',name:'Nền xanh nhạt cho phần nội dung',position:{left:40,top:130,width:1200,height:537},fill:C.surface,line:{fill:'none',width:0}});
  panel.sendToBack();
  for(const t of slide.tables.items)t.cells.block({row:0,column:0,rowCount:1,columnCount:t.columns.length??(i===3?3:2)}).assign({fill:'#D7E5FD'});
 }
 return {slides:p.slides.items.length,removedFooters:footers.records.filter(r=>r.text==='NetGuard · Nhóm 8').length};
}
