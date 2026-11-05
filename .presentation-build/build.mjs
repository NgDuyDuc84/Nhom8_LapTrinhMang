const C = { ink:'#17243B', blue:'#2563EB', muted:'#5B687C', line:'#DDE5EF', light:'#EFF5FF', green:'#137B57' };
const FONT='Arial';
function text(s, value, x,y,w,h,size=28,color=C.ink,bold=false,align='left') {
  const a=s.shapes.add({geometry:'textbox', name:value.slice(0,50), position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  a.text=value;
  a.text.style={typeface:FONT,fontSize:size,color,bold,alignment:align,verticalAlignment:'top',insets:0,autoFit:'none',wrap:'square'};
  return a;
}
function base(p,title,num,notes) {
  const s=p.slides.add({width:1280,height:720});
  s.background.fill='#FFFFFF';
  text(s,title,64,49,1152,72,44,C.ink,true);
  text(s,'NetGuard · Nhóm 8',64,675,500,24,16,C.muted);
  text(s,String(num).padStart(2,'0'),1164,675,52,24,16,C.muted,false,'right');
  s.speakerNotes.text=notes;
  return s;
}
function item(s,n,title,desc,y,x=64,w=1138){
  text(s,String(n).padStart(2,'0'),x,y,64,60,32,C.blue,true);
  text(s,title,x+88,y,w-88,48,32,C.ink,true);
  if(desc) text(s,desc,x+88,y+54,w-88,72,26,C.muted);
}
function table(s,values,x,y,width,height,widths,size=26){
  const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width,height,columnWidths:widths,values});
  t.styleOptions={headerRow:false,bandedRows:false};
  t.borders.assign({fill:C.line,width:1,style:'solid'});
  t.cells.block({row:0,column:0,rowCount:values.length,columnCount:values[0].length}).assign({fill:'#FFFFFF',textStyle:{typeface:FONT,fontSize:size,color:C.ink},margins:{left:18,right:18,top:12,bottom:12},anchor:'center'});
  t.cells.block({row:0,column:0,rowCount:1,columnCount:values[0].length}).assign({fill:C.light,textStyle:{typeface:FONT,fontSize:size,bold:true,color:C.blue}});
  return t;
}
export async function build(p,deviceImage,notes){
  let s=base(p,'',1,notes[0]);
  text(s,'ĐỒ ÁN LẬP TRÌNH MẠNG',68,95,1100,40,24,C.blue,true);
  text(s,'NetGuard',64,192,1152,150,116,C.ink,true);
  text(s,'Giám sát thiết bị và hỗ trợ\nchẩn đoán mạng LAN',70,366,1110,132,45,C.ink);
  text(s,'Nhóm 8',72,557,900,42,28,C.blue,true);

  s=base(p,'Bài toán thực tế',2,notes[1]);
  item(s,1,'Thiết bị nào đang có mặt trong mạng?','Cần một danh sách tập trung, có IP, MAC và thời điểm quan sát.',164);
  item(s,2,'Có thiết bị mới vừa kết nối?','Cần nhận biết thay đổi so với danh sách thiết bị ban đầu.',326);
  item(s,3,'Mạng chậm, nên kiểm tra từ đâu?','Cần thêm số đo để phân biệt mạng nội bộ và đường truyền phía ngoài.',488);

  s=base(p,'Mục tiêu và phạm vi',3,notes[2]);
  text(s,'Quản lý thiết bị',64,177,550,52,34,C.blue,true);
  text(s,'IP, MAC và trạng thái quan sát\nTên, ghi chú và mức tin cậy\nLịch sử xuất hiện, cảnh báo',64,259,550,180,29);
  text(s,'Theo dõi kết nối',690,177,526,52,34,C.blue,true);
  text(s,'Độ trễ RTT và tỷ lệ mất gói\nNhận định dựa trên ICMP\nSố đo và đồ thị theo thời gian',690,259,526,180,29);
  text(s,'Phạm vi chính: mạng LAN IPv4 trên Windows',64,506,1135,60,31,C.ink,true);
  text(s,'Ứng dụng giám sát và cảnh báo, không ngắt kết nối thiết bị.',64,582,1135,45,25,C.muted);

  s=base(p,'Công nghệ và kiến trúc',4,notes[3]);
  table(s,[['Tầng','Vai trò','Công nghệ'],['Giao diện','Hiển thị thiết bị, cảnh báo và RTT','PySide6, pyqtgraph'],['Backend và dịch vụ','Điều phối tác vụ nền, phát tín hiệu','Python, Qt signals'],['Xử lý mạng','Quét ARP, đo ICMP, dò đường','Scapy/Npcap, icmplib, tracert'],['Lưu trữ','Thiết bị, lịch sử và số đo','SQLite']],64,163,1152,378,[250,490,412],25);
  text(s,'Tác vụ mạng chạy ở luồng nền; giao diện nhận kết quả qua backend.',64,578,1140,62,27,C.muted);

  s=base(p,'Phát hiện thiết bị bằng ARP',5,notes[4]);
  item(s,1,'Gửi yêu cầu ARP','Quét subnet của card mạng đã chọn.',170,64,720);
  item(s,2,'Thu phản hồi IP và MAC','Ghi nhận thiết bị quan sát được trong LAN.',323,64,720);
  item(s,3,'Cập nhật trạng thái','Lưu thiết bị và lịch sử xuất hiện.',476,64,720);
  text(s,'30 giây',867,178,340,90,59,C.blue,true);
  text(s,'Chu kỳ quét cấu hình',867,275,340,48,25,C.muted);
  text(s,'3 lần',867,376,340,85,59,C.blue,true);
  text(s,'Quét hợp lệ liên tiếp\nkhông thấy mới xác nhận offline',867,472,340,110,25,C.muted);
  text(s,'Thiết bị ngủ hoặc mạng cô lập client có thể làm thiếu phản hồi ARP.',64,626,1152,35,22,C.muted);

  s=base(p,'Cảnh báo thiết bị mới',6,notes[5]);
  item(s,1,'Thu thập danh sách ban đầu','Quan sát đủ các thiết bị quen thuộc trước khi chốt baseline.',156);
  item(s,2,'Chốt baseline','Bắt đầu theo dõi thiết bị mới phát sinh sau thời điểm này.',275);
  item(s,3,'Cảnh báo thiết bị mới chưa tin cậy','Hiển thị IP, MAC và thông báo qua khay hệ thống.',394);
  item(s,4,'Người dùng kiểm tra và xác nhận','Đặt tên, ghi chú hoặc đánh dấu tin cậy.',513);
  text(s,'Baseline hiện chốt qua CLI. Nút “Tin cậy tất cả” chỉ cập nhật mức tin cậy.',64,633,1150,31,21,C.muted);

  s=base(p,'Hỗ trợ chẩn đoán bằng ICMP',7,notes[6]);
  text(s,'So sánh gateway, mốc phản hồi sau gateway và đích ngoài 1.1.1.1',64,141,1152,55,27,C.muted);
  table(s,[['Dữ liệu quan sát','Nhận định hỗ trợ kiểm tra'],['Gateway có chỉ số xấu','Nghi vấn mạng nội bộ hoặc router'],['Gateway ổn, mốc phía nhà mạng xấu','Nghi vấn đường truyền hoặc phía nhà mạng'],['Các mốc trước ổn, đích ngoài xấu','Nghi vấn Internet hoặc đích đo'],['Thiếu dữ liệu cần thiết','Chưa đủ cơ sở kết luận']],64,212,1152,328,[570,582],24);
  text(s,'Tối thiểu 10 mẫu. Cửa sổ 30 mẫu. Nhận định thông thường cần ổn định 3 chu kỳ.',64,566,1150,65,25,C.ink);
  text(s,'ICMP có thể bị hạn chế phản hồi, nên kết quả cần đối chiếu thêm.',64,632,1150,32,22,C.muted);

  s=base(p,'Giao diện quản lý thiết bị',8,notes[7]);
  text(s,'IP, MAC, mức tin cậy và thời điểm thấy gần nhất',64,141,1152,48,29,C.muted);
  s.images.add({blob:deviceImage,contentType:'image/jpeg',alt:'Giao diện thật của NetGuard: danh sách thiết bị đã lưu ở trạng thái chưa xác minh khi mất LAN',fit:'contain',position:{left:64,top:210,width:1152,height:346}});
  text(s,'Dữ liệu đã lưu cần được xác minh lại trong phiên hiện tại',64,583,1152,52,29,C.blue,true);
  text(s,'Ảnh chụp khi mất LAN; trạng thái “Chưa xác minh” tránh hiểu nhầm là đang online.',64,635,1152,31,21,C.muted);

  s=base(p,'Demo ứng dụng',9,notes[8]);
  text(s,'Thiết bị mới',64,162,540,50,34,C.blue,true);
  text(s,'1. Quét danh sách thiết bị ban đầu\n\n2. Chốt baseline bằng CLI\n\n3. Cho thiết bị mới vào cùng mạng\n\n4. Xem cảnh báo và đặt mức tin cậy',64,248,540,310,28);
  text(s,'Mất và khôi phục LAN',690,162,526,50,34,C.blue,true);
  text(s,'1. Mở tab Chẩn đoán, xem số đo\n\n2. Tắt Wi-Fi trên máy chạy ứng dụng\n\n3. Quan sát thông báo mất LAN\n\n4. Bật lại và theo dõi phép đo tiếp tục',690,248,526,310,28);
  text(s,'Chuẩn bị: Npcap, quyền Admin và mạng không cô lập client. Thiết bị mới chưa có trong dữ liệu demo.',64,614,1148,50,21,C.muted);

  s=base(p,'Kiểm thử và kết quả hiện tại',10,notes[9]);
  text(s,'65/65',64,168,560,160,112,C.blue,true);
  text(s,'bài kiểm thử tự động đạt',70,350,540,65,34,C.ink,true);
  text(s,'Lần chạy ngày 05/11/2026',70,439,540,42,25,C.muted);
  text(s,'Phạm vi kiểm thử',690,177,526,50,33,C.ink,true);
  text(s,'Quy tắc chẩn đoán và thiếu mẫu\n\nMô phỏng thay đổi thiết bị\n\nMất, khôi phục kết nối\n\nGiao diện và dữ liệu trong phiên',690,259,526,300,28,C.muted);
  text(s,'Kết quả tự động cần được bổ sung bằng đối chiếu ARP, ICMP và diễn tập trên mạng thật.',64,590,1152,66,26,C.ink);

  s=base(p,'Hạn chế và hướng phát triển',11,notes[10]);
  table(s,[['Hiện tại','Bước phát triển tiếp theo'],['ARP phụ thuộc phản hồi và cấu hình LAN','Đánh giá thêm trên các điều kiện mạng'],['ICMP hỗ trợ khoanh vùng sự cố','Đối chiếu và tinh chỉnh ngưỡng chẩn đoán'],['PDF, CSV và tra hãng MAC mới có khung','Hoàn thiện và kiểm thử các chức năng'],['Zalo mới mô phỏng nội dung thông báo','Tích hợp dịch vụ gửi thông báo thật'],['Baseline hiện thao tác qua CLI','Bổ sung thao tác trên giao diện']],64,170,1152,424,[576,576],25);
  text(s,'Phát triển tiếp dựa trên kết quả kiểm tra, phản hồi sử dụng và yêu cầu của nhóm.',64,619,1152,45,23,C.muted);

  s=base(p,'',12,notes[11]);
  text(s,'NetGuard',64,112,1152,96,73,C.ink,true);
  text(s,'Ứng dụng ARP và ICMP\ntrong giám sát mạng LAN',64,250,1152,148,48,C.blue,true);
  text(s,'Xử lý mạng nền, giao diện desktop và lưu trữ lịch sử',68,442,1140,65,31,C.muted);
  text(s,'Cảm ơn thầy/cô và các bạn',68,563,1140,58,35,C.ink,true);
  return p;
}
