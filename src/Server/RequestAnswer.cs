namespace Server
{
    /// <summary>
    /// Ket qua cua mot yeu cau (REQUEST) ma Server da gui cho may tram (giai doan 4).
    ///
    /// Co 3 truong hop deu duoc gom vao lop nay:
    ///  - may tram tra loi binh thuong (thong diep RESPONSE);
    ///  - may tram bao loi (thong diep ERROR) hoac yeu cau khong duoc ho tro;
    ///  - may tram khong tra loi trong thoi gian cho, hoac ngat ket noi giua chung.
    /// </summary>
    public class RequestAnswer
    {
        // Ten may tram da duoc yeu cau.
        public string StationName { get; set; } = "";

        // Ma yeu cau da gui, vi du Protocol.RequestStationInfo.
        public string Code { get; set; } = "";

        // Noi dung may tram tra ve (voi truong hop het thoi gian cho thi la ly do).
        public string Payload { get; set; } = "";

        // true neu day la truong hop loi (bao loi, het thoi gian cho, mat ket noi).
        public bool IsError { get; set; }

        // Thoi gian tu luc gui yeu cau den luc co ket qua, tinh bang mili giay.
        public int ElapsedMs { get; set; }
    }
}
