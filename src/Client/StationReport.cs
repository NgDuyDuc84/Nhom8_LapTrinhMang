using System.Runtime.InteropServices;
using System.Text;
using Common;

namespace Client
{
    /// <summary>
    /// Giai doan 4: thu thap thong tin cua may tram nay de tra loi yeu cau cua Server.
    ///
    /// Ket qua la mot chuoi dang "khoa=gia tri; khoa=gia tri; ..." (xem Protocol.FieldSeparator).
    /// Chon dang chuoi chu thuong thay vi JSON long trong JSON de khi bat goi tin bang
    /// Wireshark van doc duoc noi dung bang mat tren mot dong.
    /// </summary>
    public static class StationReport
    {
        /// <summary>
        /// Thu thap thong tin may tram. Nem loi neu khong doc duoc (khi do phia giao dien
        /// se tra ERROR cho Server thay vi RESPONSE).
        /// </summary>
        public static string Build()
        {
            StringBuilder text = new StringBuilder();

            AppendField(text, "May", Environment.MachineName);
            AppendField(text, "Nguoi dung", Environment.UserName);
            AppendField(text, "He dieu hanh", RuntimeInformation.OSDescription);
            AppendField(text, "Kien truc", RuntimeInformation.OSArchitecture.ToString());
            AppendField(text, "Nen tang", RuntimeInformation.FrameworkDescription);
            AppendField(text, "So luong CPU", Environment.ProcessorCount + " luong");
            AppendField(text, "Thoi gian may da chay", FormatUptime());
            AppendField(text, "O dia he thong", DescribeSystemDrive());
            AppendField(text, "Thu muc lam viec", Environment.CurrentDirectory);

            return text.ToString();
        }

        /// <summary>Them mot truong "khoa=gia tri" vao chuoi, tu dong them dau ngan cach.</summary>
        private static void AppendField(StringBuilder text, string key, string value)
        {
            if (text.Length > 0)
            {
                text.Append(Protocol.FieldSeparator);
            }

            text.Append(key).Append('=').Append(value);
        }

        /// <summary>
        /// Thoi gian tu luc may duoc bat (khong phai tu luc mo chuong trinh)
        /// de nguoi quan tri biet may tram da chay lien tuc bao lau.
        /// </summary>
        private static string FormatUptime()
        {
            TimeSpan uptime = TimeSpan.FromMilliseconds(Environment.TickCount64);

            return uptime.Days + " ngay " + uptime.Hours + " gio " + uptime.Minutes + " phut";
        }

        /// <summary>
        /// Dung luong con trong cua o dia chua he dieu hanh.
        /// O dia co the khong doc duoc (vi du o dia mang da bi ngat) nen phai bat loi rieng,
        /// ghi ro ly do thay vi bo trong.
        /// </summary>
        private static string DescribeSystemDrive()
        {
            try
            {
                string root = Path.GetPathRoot(Environment.SystemDirectory);
                DriveInfo drive = new DriveInfo(root);

                return root + " con " + ToGb(drive.AvailableFreeSpace)
                       + " GB / " + ToGb(drive.TotalSize) + " GB";
            }
            catch (Exception ex)
            {
                return "khong doc duoc (" + ex.Message + ")";
            }
        }

        /// <summary>Doi so byte thanh chuoi GB cho de doc.</summary>
        private static string ToGb(long bytes)
        {
            return (bytes / 1024.0 / 1024.0 / 1024.0).ToString("0.0");
        }
    }
}
