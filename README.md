# 🏥 Vitabi - Healthcare Platform

> A comprehensive healthcare platform connecting patients with hospitals worldwide, featuring multilingual support, symptom checking, and hospital booking services.

## 📋 What & Why

**Vitabi** is a modern healthcare platform designed to bridge the gap between patients and healthcare providers globally. Built with Django, it offers a seamless experience for patients to find, review, and book appointments with hospitals while providing multilingual support for international users.

The platform addresses the critical need for accessible healthcare information and services, especially for travelers and expatriates who need reliable medical care in foreign countries.

## ✨ Key Features

- 🌍 **Multilingual Support** - English, Japanese, and Vietnamese
- 🏥 **Hospital Discovery** - Find hospitals by location with Google Maps integration
- 📅 **Appointment Booking** - Schedule hospital visits with flexible time slots
- 🔍 **Symptom Checker** - AI-powered symptom analysis and recommendations
- ⭐ **Review System** - Patient reviews and ratings for hospitals
- 🛡️ **Insurance Integration** - Support for various insurance providers
- 📱 **Responsive Design** - Mobile-friendly interface
- 🌐 **Global Coverage** - Hospitals from multiple countries
- 📊 **Real-time Data** - Live hospital availability and working hours

## 🛠️ Technologies Used

- **Backend**: Django 4.2.7, Python 3.8+
- **Database**: PostgreSQL
- **Frontend**: HTML5, CSS3, JavaScript
- **Maps**: Google Maps API
- **Translation**: Google Translate API
- **Cloud**: Google Cloud Platform
- **Deployment**: Heroku
- **Additional**: Celery, Redis, Pillow, GeoPy

## 🚀 Installation & Setup

### Prerequisites
- Python 3.8+
- PostgreSQL
- Google Cloud account with Maps API enabled

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/khoilieu/vitabi-healthcare-platform-django.git
   cd vitabi-healthcare-platform-django
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment setup**
   ```bash
   cp .env.example .env
   ```
   
   Configure your `.env` file:
   ```env
   GOOGLE_MAPS_API_KEY=your_google_maps_api_key
   GOOGLE_CUSTOM_SEARCH_API_KEY=your_search_api_key
   GOOGLE_CUSTOM_SEARCH_CX=your_search_cx
   DATABASE_URL=your_postgresql_url
   SECRET_KEY=your_secret_key
   ```

5. **Database setup**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

6. **Run the development server**
   ```bash
   python manage.py runserver
   ```

7. **Access the application**
   Open your browser and navigate to `http://localhost:8000`

## 📖 Usage Guide

*Đang cập nhật*

## 📸 Screenshots & Demo

*Đang cập nhật*

## 📊 Project Status

- ✅ **Core Features**: Hospital discovery, booking system, user management
- ✅ **Multilingual Support**: English, Japanese, Vietnamese
- ✅ **Database Integration**: PostgreSQL with Django ORM
- ✅ **API Integration**: Google Maps, Google Translate
- 🔄 **In Progress**: Advanced symptom checker, mobile app
- 📋 **Planned**: Real-time notifications, video consultations

## 👨‍💻 Author & Contact

**Khôi Liêu**

- 📧 **Email**: [khoilieuct03@gmail.com](mailto:khoilieuct03@gmail.com)
- 💼 **LinkedIn**: [https://www.linkedin.com/in/lieu-khoi-6b4a09322/](https://www.linkedin.com/in/lieu-khoi-6b4a09322/)
- 🐙 **GitHub**: [@khoilieu](https://github.com/khoilieu)

---

<div align="center">
  <p>Made with ❤️ for better healthcare accessibility</p>
  <p>© 2024 Vitabi Healthcare Platform</p>
</div>