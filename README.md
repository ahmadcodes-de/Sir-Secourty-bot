# 🛡️ SIR | Security Bot

[English](#-english) | [Deutsch](#-deutsch) | [العربية](#-العربية)

---

## 🇬🇧 English

A professional, modular Discord bot focused on security, server administration, and advanced event logging.

### ✨ Core Features

*   **🛡️ Security:** Advanced auto-protection, raid prevention, and rate limiting.
*   **🛠️ Administration:** Full command suite (`/kick`, `/ban`, `/lock`, etc.).
*   **📝 Event Logging:** Comprehensive tracking of member, channel, role, and guild events.
*   **🎨 UI/UX:** Interactive Modals, Views, and Selects for a premium user experience.

### 📁 Project Structure

The project is built with a clean, modular architecture:

```text
SIR | Security Bot/
├── .env                       # Environment variables (Bot Token)
├── config.py                  # Configuration, colors, and emojis
├── keep_alive.py              # Script to keep the bot running 24/7
├── main.py                    # Main execution and entry point
├── README.md                  # Project documentation
├── requirements.txt           # Required Python libraries
│
├── Admin/
│   ├── .env                   # Local environment file for Admin module
│   └── mod.py                 # Moderation and admin core logic
│
├── cogs/
│   ├── __init__.py            # Marks directory as a Python package
│   ├── admin.py               # Administrative commands
│   ├── automod.py             # Automated moderation features
│   ├── developer_presence.py  # Rich presence and status management
│   ├── events.py              # General Discord event listeners
│   ├── general.py             # General/Utility user commands
│   ├── info.py                # Information commands (user, server, bot)
│   ├── logs.py                # Logging system triggers
│   └── protection.py          # Security and anti-raid features
│
├── database/
│   ├── __init__.py            # Marks directory as a Python package
│   ├── db_manager.py          # SQLite database connections and queries
│   └── guild_presence_settings.json # Saved database settings for guilds
│
├── events/
│   ├── __init__.py            # Marks directory as a Python package
│   ├── channel_events.py      # Listeners for channel creation/deletion/updates
│   ├── guild_events.py        # Listeners for server updates and joins
│   ├── member_events.py       # Listeners for member joins, leaves, and role changes
│   └── role_events.py         # Listeners for role creation/deletion/updates
│
├── ui/
│   ├── __init__.py            # Marks directory as a Python package
│   ├── log_views.py           # Views specialized for the log system
│   ├── modals.py              # Interactive text input popups
│   ├── selects.py             # Interactive dropdown menus
│   └── views.py               # Component layouts (Buttons, etc.)
│
└── utils/
    ├── __init__.py            # Marks directory as a Python package
    ├── auto_protection.py     # Automated background security loops
    ├── helpers.py             # Global helper functions and embeds
    ├── protection.py          # Core security functions
    └── strings.py             # Multi-language translation dictionaries

```

---

## 🇩🇪 Deutsch

Ein professioneller, modularer Discord-Bot mit Fokus auf Sicherheit, Server-Administration und erweitertes Event-Logging.

### ✨ Hauptfunktionen

* **🛡️ Sicherheit:** Erweiterter Schutz, Raid-Prävention und Ratenbegrenzung.
* **🛠️ Administration:** Umfassendes Befehls-Set (`/kick`, `/ban`, `/lock`, etc.).
* **📝 Event-Logging:** Detaillierte Nachverfolgung von Mitgliedern, Kanälen, Rollen und Server-Ereignissen.
* **🎨 UI/UX:** Interaktive Modals, Views und Selects für eine erstklassige Benutzererfahrung.

### 📁 Projektstruktur

Das Projekt nutzt eine saubere, modulare Architektur:

```text
SIR | Security Bot/
├── .env                       # Umgebungsvariablen (Bot-Token)
├── config.py                  # Konfiguration, Farben und Emojis
├── keep_alive.py              # Skript zur 24/7-Online-Erhaltung
├── main.py                    # Hauptskript zum Starten des Bots
├── README.md                  # Projektdokumentation
├── requirements.txt           # Erforderliche Python-Bibliotheken
│
├── Admin/
│   ├── .env                   # Lokale Umgebungsvariable für Admin-Modul
│   └── mod.py                 # Kernlogik für Moderation und Administration
│
├── cogs/
│   ├── __init__.py            # Markiert das Verzeichnis als Python-Paket
│   ├── admin.py               # Administrative Befehle
│   ├── automod.py             # Automatisierte Moderationsfunktionen
│   ├── developer_presence.py  # Verwaltung von Bot-Status und Präsenz
│   ├── events.py              # Allgemeine Discord-Event-Listener
│   ├── general.py             # Allgemeine Benutzerbefehle
│   ├── info.py                # Informationsbefehle (Benutzer, Server, Bot)
│   ├── logs.py                # Steuerung des Logging-Systems
│   └── protection.py          # Sicherheits- und Anti-Raid-Funktionen
│
├── database/
│   ├── __init__.py            # Markiert das Verzeichnis als Python-Paket
│   ├── db_manager.py          # SQLite-Datenbankverbindungen und Abfragen
│   └── guild_presence_settings.json # Gespeicherte Datenbankeinstellungen für Server
│
├── events/
│   ├── __init__.py            # Markiert das Verzeichnis als Python-Paket
│   ├── channel_events.py      # Überwachung von Kanal-Erstellung/Löschung/Updates
│   ├── guild_events.py        # Überwachung von Server-Updates und Beitritten
│   ├── member_events.py       # Überwachung von Mitglieder-Beitritten/Verlassen/Rollen
│   └── role_events.py         # Überwachung von Rollen-Erstellung/Löschung/Updates
│
├── ui/
│   ├── __init__.py            # Markiert das Verzeichnis als Python-Paket
│   ├── log_views.py           # Spezialisierte Ansichten für das Log-System
│   ├── modals.py              # Interaktive Formulare (Texteingabe)
│   ├── selects.py             # Interaktive Dropdown-Menüs
│   └── views.py               # Komponenten-Layouts (Buttons, etc.)
│
└── utils/
    ├── __init__.py            # Markiert das Verzeichnis als Python-Paket
    ├── auto_protection.py     # Automatisierte Sicherheits-Hintergrundprozesse
    ├── helpers.py             # Globale Hilfsfunktionen und Embeds
    ├── protection.py          # Kernfunktionen für den Serverschutz
    └── strings.py             # Wörterbücher für Mehrsprachigkeit

```

---

## 🇦🇷 العربية

بوت Discord احترافي، معياري (Modular)، يركز على الحماية، إدارة السيرفرات، وتتبع الأحداث (Logging) بشكل متقدم.

### ✨ المميزات الرئيسية

* **🛡️ الحماية:** نظام حماية تلقائي متطور، منع الإغارات (Raid)، ونظام Rate Limiting.
* **🛠️ الإدارة:** مجموعة أوامر إدارية كاملة (`/kick`, `/ban`, `/lock` وغيرها).
* **📝 نظام السجلات:** تتبع دقيق لأحداث الأعضاء، القنوات، الرتب، وتغييرات السيرفر.
* **🎨 واجهات المستخدم:** استخدام Modals و Views و Selects لتوفير تجربة مستخدم تفاعلية واحترافية.

### 📁 هيكل المشروع

تم تصميم المشروع بهيكلية منظمة وسهلة التوسع:

```text
SIR | Security Bot/
├── .env                       # متغيرات البيئة (يحتوي على الـ Token)
├── config.py                  # الإعدادات العامة، الألوان، والإيموجي
├── keep_alive.py              # سكربت لإبقاء البوت يعمل 24/7 دون انقطاع
├── main.py                    # ملف التشغيل الرئيسي للبوت
├── README.md                  # ملف توثيق المشروع الحالي
├── requirements.txt           # الحزم والمكتبات المطلوبة للتشغيل
│
├── Admin/
│   ├── .env                   # ملف بيئة محلي خاص بمجلد الإدارة
│   └── mod.py                 # المنطق البرمجي الأساسي للإدارة والرقابة
│
├── cogs/
│   ├── __init__.py            # لتعريف المجلد كحزمة بايثون (Package)
│   ├── admin.py               # أوامر الإدارة والتحكم بالأعضاء
│   ├── automod.py             # نظام الرقابة التلقائي (Auto-mod)
│   ├── developer_presence.py  # إدارة حالة البوت ونصوص الـ Presence للمطور
│   ├── events.py              # مستمعات الأحداث العامة لـ Discord
│   ├── general.py             # الأوامر العامة وأدوات المستخدمين
│   ├── info.py                # أوامر المعلومات (عضو، سيرفر، بوت)
│   ├── logs.py                # التحكم وإدارة موديول السجلات
│   └── protection.py          # أوامر الحماية ومنع الإغارات
│
├── database/
│   ├── __init__.py            # لتعريف المجلد كحزمة بايثون
│   ├── db_manager.py          # الاتصال بقاعدة البيانات وتنفيذ الاستعلامات
│   └── guild_presence_settings.json # إعدادات حالة السيرفرات المحفوظة
│
├── events/
│   ├── __init__.py            # لتعريف المجلد كحزمة بايثون
│   ├── channel_events.py      # تتبع أحداث القنوات (إنشاء، حذف، تعديل)
│   ├── guild_events.py        # تتبع أحداث السيرفر بشكل عام
│   ├── member_events.py       # تتبع أحداث الأعضاء (انضمام، مغادرة، رتب)
│   └── role_events.py         # تتبع أحداث الرتب (إنشاء، حذف، تعديل)
│
├── ui/
│   ├── __init__.py            # لتعريف المجلد كحزمة بايثون
│   ├── log_views.py           # واجهات تفاعلية مخصصة لنظام السجلات
│   ├── modals.py              # النوافذ المنبثقة لإدخال البيانات (Modals)
│   ├── selects.py             # القوائم المنسدلة التفاعلية (Select Menus)
│   └── views.py               # واجهات الأزرار والمكونات الأساسية
│
└── utils/
    ├── __init__.py            # لتعريف المجلد كحزمة بايثون
    ├── auto_protection.py     # عمليات الفحص التلقائية والخلفية للحماية
    ├── helpers.py             # الدوال المساعدة العامة وتنسيق الـ Embeds
    ├── protection.py          # الدوال الأساسية لمنطق الحماية والأمان
    └── strings.py             # ملف النصوص والترجمة متعدد اللغات

```

### 🚀 التشغيل السريع

1. **التثبيت:** `pip install -r requirements.txt`
2. **الإعداد:** قم بتعبئة `DISCORD_TOKEN` في ملف `.env`.
3. **التشغيل:** `python main.py`

---

⭐ **إذا أعجبك المشروع، لا تنسَ إعطاءه نجمة على GitHub!**

```
