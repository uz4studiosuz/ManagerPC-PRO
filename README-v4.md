# ManagerPC 4 — Veyonsiz sinf boshqaruvi

Windows 10/11 x64 uchun. O‘qituvchi va o‘quvchi kompyuterlariga Python yoki Veyon kerak emas. Dastur sinovdan o‘tkaziladigan birinchi mahalliy versiya: avval bitta maktab kompyuteriga o‘rnating.

## O‘qituvchi kompyuterida

1. Eski ManagerPC qora oynasini yoping.
2. `ManagerPC-4` papkasidan `ADMIN-START.bat` ni oching. Admin dastur, `index.html`, `app.js`, `style.css` va ikkala agent EXE shu papkada tursin.
3. Xususiy sinf tarmog‘i uchun `ADMIN-FIREWALL.bat` ni **Run as administrator** bilan bir marta oching. Bu faqat xususiy profil va mahalliy subnetdan TCP 8766 portiga ruxsat beradi. Maktab tarmog‘i Public/Domain bo‘lsa, IT administratori mos ruxsatni sozlasin.
4. Paneldagi **O‘rnatish** bo‘limiga o‘ting. `ipconfig` dagi sinf Ethernet IPv4 manzilini kiriting va **Agent paketini yuklab olish** ni bosing.
5. Olingan ZIP paketni o‘quvchi kompyuterlariga ko‘chiring. Paket 8 soat davomida yangi kompyuterlarni ulashga ruxsat beradi. Uning ichida server sertifikati va vaqtli ulanish kaliti bor; uni boshqalarga tarqatmang.

## O‘quvchi kompyuterida — bir marta

1. ZIP’ni alohida papkaga chiqaring. Fayllarni ZIP ichidan to‘g‘ridan-to‘g‘ri ochmang.
2. `AGENT-INSTALL.bat` ustiga o‘ng tugma → **Run as administrator**.
3. O‘rnatish tugagach Windows hisobidan chiqing va qayta kiring. **IP va kalit yozish kerak emas.**
4. Admin panelda kompyuter hostname bilan paydo bo‘ladi. Desktop yordamchisi ulanganidan keyin ekran tayyor bo‘ladi.

O‘rnatuvchi SYSTEM hisobidagi agentni kompyuter yoqilganda, alohida Desktop yordamchisini esa foydalanuvchi Windows hisobiga kirganda ishga tushiradi. 1.x agentlarni ham shu yangi paket bilan yangilang. 4.0 server eski HTTP agentlarni qabul qilmaydi. Bir xil hostname ikki xil kompyuterda ishlatilmasin.

## Nimalar ishlaydi

- Kompyuterlar kartalari, hostname/IP qidiruvi, onlayn/oflayn filtri.
- Jonli ekranlar: asosiy monitor, taxminan 1 kadr/soniya, bir vaqtda 24 tagacha qurilma.
- Alohida ekranni kattaroq ko‘rish; sichqoncha, scroll, klaviatura, Unicode matn yuborish.
- Ekran rasmini o‘qituvchi kompyuteriga qo‘lda saqlash.
- Oynasi ochiq dasturlar, barcha ishlayotgan jarayonlar, odatiy papkalarda topilgan EXE’lar alohida ro‘yxatlarda.
- Dasturlarni qidirish, 20 tadan sahifalash, EXE’ni blok ro‘yxatiga qo‘shish, qayta skanerlash.
- Bitta yoki barcha onlayn kompyuterlarga xabar yuborish va HTTP/HTTPS sayt ochish.
- Windows’ni qulflash. Uni qayta ochish uchun o‘quvchi o‘z Windows paroli bilan kiradi.
- 60 soniyali “Darsga e’tibor” oynasi; Esc yoki yopish tugmasi bilan chiqish mumkin. Bu Windows’ni xavfsiz qulflash o‘rnini bosmaydi.
- 30 soniyadan keyin qayta yoqish/o‘chirish va kutish vaqtida bekor qilish. Bu amallar panelda tasdiqlanadi; saqlanmagan ish yo‘qolishi mumkin.
- Sayt va dasturlar uchun umumiy/shaxsiy qoidalar, zaxira olish va qayta tiklash.
- Chrome/Edge URLBlocklist va Windows hosts orqali sayt qoidalari; ManagerPC qo‘shgan brauzer qoidalarigina olib tashlanadi.
- CPU yadro soni, RAM, diskdagi bo‘sh joy, foydalanuvchi va ulanish holati.
- Buyruq navbati, bajarilish natijasi, xatolar va joriy sessiyadagi oxirgi 250 hodisa jurnali.
- Har bir kompyuter uchun alohida kalit, ulanishni bekor qilish, HTTPS va server sertifikatini tekshirish.

## Ekranni boshqarish

**Kompyuterlar → qurilmani tanlash → Ekranni ko‘rish → Boshqaruvni yoqish.** Keyin ekran tasviri ustiga bosing. Brauzer yoki Windows ushlab qoladigan Alt+Tab kabi ayrim tugmalar uzatilmaydi. UAC, Windows login/lock ekrani va administrator sifatida ochilgan ilovalar cheklovlariga amal qilinadi; dastur ularni chetlab o‘tmaydi. Hozircha faqat jismoniy konsoldagi faol foydalanuvchining asosiy monitori qo‘llab-quvvatlanadi, RDP sessiyalari va boshqa monitorlar emas.

O‘quvchi kompyuterida ManagerPC belgisi ko‘rinadi: kuzatuv/boshqaruv holati va 5 daqiqali mahalliy pauza tugmasi bor. Kuzatuv faqat panelda yoqilganda boshlanadi. Panel yopilgach sessiya ko‘pi bilan 15 soniyada tugaydi; aloqa yo‘qolganda ushlab turilgan tugmalar bo‘shatiladi. Ekran tasvirlari server xotirasida qisqa saqlanadi, avtomatik disk arxivi yaratilmaydi.

## Qoidalar va chegaralar

Qoidani yozib **Saqlash**ni bosish kerak. Agent so‘nggi qabul qilingan qoidalarni diskda saqlaydi: admin panel yopilsa va o‘quvchi PC qayta yoqilsa ham qo‘llaydi. Dastur bloki ishga tushirishni operatsion tizim darajasida taqiqlamaydi: topilgan jarayonni odatda 2 soniyalik tekshiruvda yopadi. Nomini o‘zgartirish, boshqa brauzer, VPN yoki administrator huquqi bilan chetlab o‘tish mumkin. “Barcha dasturlar” diskning to‘liq inventari emas.

Chrome/Edge URL siyosati domen va subdomenlarni qamraydi, lekin brauzer siyosatni yangilashi yoki qayta ochilishi kerak bo‘lishi mumkin. Mavjud enterprise allowlist/bloklist, Edge profil turi va tashkilot siyosati ustun bo‘lishi mumkin. Boshqa brauzerlar uchun hosts usuli qoladi. Tarmoqdagi qat’iy nazorat uchun maktab router/DNS siyosatlari ham zarur.

## Olib tashlash va ma’lumotlar

- O‘quvchi kompyuterida `AGENT-REMOVE.bat` ni administrator sifatida ochish avtomatik ishga tushish, xizmat jarayonlari va ManagerPC qo‘shgan hosts/brauzer qoidalarini to‘xtatadi. Fayllar qayta o‘rnatish uchun qoladi.
- Admin sozlamalari: `%LOCALAPPDATA%\ManagerPC`. Bu papkada maxfiy server kaliti bor; faqat ishonchli administratorga tegishli bo‘lsin.
- Agent: `C:\ProgramData\ManagerPC-Agent`; maxfiy agent kaliti `service\config.json` da, faqat SYSTEM va administratorlar o‘qiydi.
- Desktop yordamchisining alohida, faqat shu kompyuterga tegishli kaliti `desktop.json` da.
- Agent xatolari: `last-error.txt` yoki `install-error.txt`. Desktop xatolari: `%LOCALAPPDATA%\ManagerPC-Desktop\error.txt`.
- **Ulanish kalitini bekor qilish** tarmoq ulanishini bekor qiladi; mahalliy saqlangan qoidalarni o‘chirmaydi. Butunlay olib tashlash uchun uninstall faylidan foydalaning.

## Tekshiruv va qayta yig‘ish

12 ta avtomatlashtirilgan test: haqiqiy loopback HTTPS almashinuvi, rol va kalit izolyatsiyasi, CSRF, sertifikatni tekshirish, ekran oqimi, buyruq muddati/deduplikatsiya, revoke va brauzer qoidalarining qaytarilishi. Brauzer sinovi kompyuter tanlash, ro‘yxatlar, sahifalash, blok saqlash, sintetik ekran oqimi va mobil ko‘rinishni tekshiradi. Haqiqiy ikkita sinf PC o‘rtasidagi tezlik, Windows startup va barcha antivirus kombinatsiyalari hali tekshirilmagan.

Manba kirish nuqtalari: `server_v4.py`, `agent_v4.py`, `desktop_agent.py`. Yig‘ish uchun `build-v4.ps1`; test uchun `python -m unittest -v test_v4`. Windows x64’da Python, Pillow, psutil, pywin32, cryptography va PyInstaller kerak; tayyor foydalanuvchi EXE’lari uchun kerak emas.

Rasmiy texnik manbalar: [Windows interaktiv sessiyalari](https://learn.microsoft.com/en-us/windows/win32/services/interactive-services), [SendInput cheklovlari](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput), [Edge URLBlocklist](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-browser-policies/urlblocklist).
