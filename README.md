# 🎓 CertFlow

> **Automated Certificate Generation & Personalized Email Distribution Platform**

**CertFlow** is an all-in-one web application designed for colleges, event organizers, educators, hackathon committees, and conference hosts. It allows you to design custom certificates, automatically generate hundreds or thousands of high-resolution personalized PDFs, and email them directly to every participant using your own Google / Gmail account in just a few clicks.

---

## 🌟 Why CertFlow?

* **No Manual Work:** Stop manually typing names onto certificates one by one.
* **Direct-to-Inbox Delivery:** Emails are sent through your authenticated Gmail or College Google Workspace account, ensuring your emails land directly in the recipient's **Primary Inbox** (never in Spam or Promotions).
* **Live Visual Certificate Designer:** Upload any certificate background image, pick from elegant typography styles, and position the participant's name with real-time visual feedback.
* **Google Drive Integration:** All generated certificates are automatically organized into folders in your Google Shared Drive.
* **Safe & Resilient:** If your internet disconnects or you hit a daily limit, CertFlow never sends duplicates and resumes right where you left off.

---

## 🚀 How It Works — 5-Step Process

```
  [ 1. Connect Gmail ] ──▶ [ 2. Create Campaign ] ──▶ [ 3. Design Certificate ] ──▶ [ 4. Generate PDFs ] ──▶ [ 5. Send via Gmail ]
```

### Step 1: Connect Your Gmail (One-Time Setup)
1. Navigate to **Settings** in CertFlow.
2. Under **Gmail Integration**, click **Connect Gmail**.
3. Authorize your Google account on the Google consent screen.
4. Once connected, your email address is linked and ready to send official certificate emails.
*(Optional: Use the "Send Test Email" tool to send a demo email to yourself and verify everything is working).*

### Step 2: Create a Campaign & Upload Participants
1. Click **New Campaign** on the Campaigns page.
2. Enter your **Campaign / Event Name** (e.g., *NIRMAN 6.0* or *National Tech Summit 2026*).
3. Upload your participant spreadsheet (`.xlsx`, `.xls`, or `.csv`) containing participant names and email addresses.
4. Click **Create Campaign**. All participants will be loaded into your campaign queue automatically.

### Step 3: Design Your Certificate in Certificate Studio
1. Open your campaign and select the **Certificate Studio** tab (or click **Design Certificate**).
2. **Upload Certificate Background:** Upload your blank certificate design image (`.png` or `.jpg`).
3. **Select Typography:** Choose from curated Google Fonts:
   * **Playfair Display**: Luxury serif (classic for formal academic degrees & awards)
   * **Great Vibes**: Flowing calligraphy script (traditional certificate look)
   * **Cinzel**: Roman classical & imperial serif
   * **Montserrat**: Modern, clean geometric sans-serif
   * **Alex Brush**: Elegant signature-style cursive
4. **Position the Name:** Use the Horizontal (X%) and Vertical (Y%) sliders to place the participant's name exactly where you want it.
5. **Customize Styling:** Adjust font size and choose colors (such as *Luxury Gold*, *Royal Navy*, or custom hex).
6. **Live Preview:** View the real-time sample canvas with different participant names.
7. Click **Save Design Coordinates**.

### Step 4: Generate All Certificates
1. Click **Generate All Participant Certificates**.
2. CertFlow will automatically render high-resolution 300 DPI PDF certificates for every participant.
3. Each certificate is saved into your Google Shared Drive in a dedicated folder named after your event (e.g. `CertFlow / Campaigns / NIRMAN 6.0 / certificates`).

### Step 5: Compose Email & Distribute
1. Switch to the **Email Distribution** tab.
2. Select one of the **Quick Templates** (e.g. *🎓 Professional Certificate*, *🚀 Tech Summit & Hackathon*, or *📜 Workshop & Seminar*) or write your own custom message.
3. Use dynamic variable tags like `{{name}}`, `{{event_name}}`, `{{certificate_id}}`, and `{{date}}` to personalize every email.
4. Click **Preview Email** to see exactly what recipients will receive.
5. Check the confirmation checkbox:
   `☑ I explicitly confirm and authorize sending personalized certificate emails...`
6. Click **Send Campaign Emails**!
7. Watch the live progress bar move in real time from **Queued** to **Processing** to **Sent (100% Complete)**.

---

## 📊 Software Capacity & Limits Chart

CertFlow is engineered to handle small workshops up to large college fests and national symposiums.

### 1. Certificate Generation & Storage Capacity

| Feature | Capacity / Limit | Details |
| :--- | :--- | :--- |
| **Generation Speed** | **1,500 to 2,400 certificates / hour** (~25–40 per minute) | Powered by high-speed Python image rendering at 300 DPI print quality. |
| **Participants per Campaign** | **1,000 to 10,000+ recipients** | No software ceiling. Bounded batch engine prevents memory overload. |
| **PDF Attachment Size** | **~200 KB to 500 KB per certificate** | Lightweight, high-resolution vector PDF format (well within Gmail's 25 MB limit). |
| **Google Shared Drive Storage** | **Up to 400,000 files per drive** | Standard Google Workspace limit. Easily holds years of past events. |
| **Database Capacity** | **Unlimited records** | Cloud Firestore serverless storage scales automatically with your events. |

---

### 2. Daily Email Dispatch Quotas (Google / Gmail)

Because emails are sent through official Google accounts to guarantee primary inbox delivery, Google's daily sending limits apply:

| Google Account Type | Daily Sending Limit | Best Suited For |
| :--- | :--- | :--- |
| **Personal Gmail Account** (`...@gmail.com`) | **500 emails / rolling 24 hours** | Department seminars, workshops, classroom competitions (up to 500 attendees). |
| **Google Workspace / College Domain** (`...@mitaoe.ac.in` or custom domain) | **2,000 emails / rolling 24 hours** | College fests, national hackathons, annual conferences (NIRMAN 6.0). |

---

### 3. Built-In Safeguards

* **Anti-Spam Throttling:** CertFlow sends emails with a built-in `0.25s` delay between recipients (~4 emails per second) to keep your account safe from Google's automated burst-rate triggers.
* **Safe Multi-Day Sending (Automatic Resume):** If your event has **3,500 participants** (exceeding Google's single-day 2,000 limit):
  * CertFlow sends the first 2,000 emails on Day 1.
  * On Day 2, simply click **Resume** — CertFlow automatically starts with participant **#2,001** and never sends duplicates.
* **Pause & Cancel Controls:** You can pause, resume, or cancel any active campaign dispatch at any moment directly from the dashboard.
* **Retry Failed Sends:** If any individual recipient had an invalid or bounced email address, click **Retry Failed Sends** to re-attempt delivery without re-sending to anyone else.

---

## 🔒 Security & Privacy

* **Token Encryption:** All Google OAuth refresh tokens are encrypted at rest using industry-standard AES-128 Fernet cryptography.
* **Strict Ownership:** Organizers can only view and manage their own campaigns and recipient lists.
* **Zero Password Storage:** Authentication is managed directly via secure Google Sign-In and Firebase Auth.

---

## 💡 Quick Tips for Organizers

1. **Spreadsheet Columns:** Make sure your participant spreadsheet has a column for `Name` (or `Full Name`) and `Email`.
2. **Template Orientation:** Landscape orientation (`1920x1080` or A4 Landscape) works best for certificate backgrounds.
3. **Double-Check Preview:** Always click **Preview Email** and **Refresh Preview** in Certificate Studio before clicking Send.
4. **Use Official Domains When Possible:** Using a `@college.edu` or company Google Workspace account allows you to send up to **2,000 emails per day** instead of 500.

---

Developed with ❤️ for event organizers and academic institutions.