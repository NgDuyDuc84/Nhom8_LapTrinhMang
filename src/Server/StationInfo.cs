using System.Net.Sockets;

namespace Server
{
    /// <summary>
    /// Thong tin cua mot may tram (Client) dang duoc Server quan ly.
    /// </summary>
    public class StationInfo
    {
        // Ten may, lay tu truong "from" cua thong diep REGISTER.
        public string Name { get; set; } = "";

        // Dia chi IP cua may tram trong mang LAN.
        public string Ip { get; set; } = "";

        // Trang thai: "Online" hoac "Offline".
        public string Status { get; set; } = "Online";

        // Thoi diem lien lac gan nhat (luc nhan duoc thong diep cuoi cung).
        public DateTime LastSeen { get; set; } = DateTime.Now;

        // Ket noi TCP dang mo cua may tram nay.
        // Giai doan 1 chi luu lai de biet may tram con ket noi hay khong,
        // cac giai doan sau (gui NOTIFY) se dung lai.
        public TcpClient Client { get; set; }

        // Doi tuong de ghi thong diep xuong ket noi TCP cua may tram nay.
        public StreamWriter Writer { get; set; }

        // Giai doan 3: Server co the ghi xuong cung mot ket noi tu hai luong khac nhau
        // (luong giao dien khi bam nut gui, va luong dang doc du lieu khi tra ACK).
        // Neu hai luong cung goi WriteLine thi hai dong JSON se bi xen vao nhau
        // va ben nhan khong tach duoc thong diep, nen phai khoa lai khi ghi.
        public readonly object WriteLock = new object();
    }
}
