# 📚 Study Lens: 웹캠 기반 공부시간 자동 측정 솔루션

![Project Status](https://img.shields.io/badge/Status-Active-brightgreen)
![Python](https://img.shields.io/badge/Python-3.9-blue?logo=python)
![YOLOv5](https://img.shields.io/badge/AI-YOLOv5-orange)
![Django](https://img.shields.io/badge/Server-Django-092E20?logo=django)
![Android](https://img.shields.io/badge/Client-Android-3DDC84?logo=android)

> **"책상 앞에 앉아 책을 펼치면 기록 시작, 자리를 비우면 기록 정지."** > Study Lens는 별도의 조작 없이, 오직 사용자의 행동(공부)만을 인식하여 시간을 기록하고 시각화해주는 스마트 공부 추적 시스템입니다.

---

## 📖 프로젝트 개요 (Overview)

**Study Lens**는 웹캠과 딥러닝(YOLOv5)을 활용하여 **"사람 + 책"**이 동시에 감지될 때만 유효한 공부 시간으로 인정합니다.
단순히 시간을 재는 것을 넘어, 공부하는 순간을 자동으로 캡처하여 **'오늘의 공부 모습'**을 갤러리 형태로 제공, 학습 동기 부여를 극대화합니다.

### ✨ 핵심 기능
- **자동 감지 (Hands-free):** 시작/정지 버튼을 누를 필요 없이 책을 펴고 앉으면 기록이 시작됩니다.
- **부재중 정지 (Auto-Pause):** 책을 치우거나 자리를 비우면 즉시 공부 기록이 멈춥니다.
- **이미지 블로그 (Visual Log):** 공부 중인 내 모습을 자동으로 남겨, 하루의 노력을 시각적으로 확인합니다.

---

## 🏗️ 시스템 아키텍처 (System Architecture)

전체 시스템은 **Edge Device(감지), Server(저장/처리), Mobile App(시각화)**의 3단계 구조로 이루어져 있습니다.

```
[Edge: Webcam + YOLOv5]
   ├─ 실시간 객체 감지 (Person + Book)
   ├─ 상태 전환(Start/Stop) 로직 수행
   └─ 캡처 이미지 + 이벤트 서버 전송
            │
            ▼
[Django Server]
   ├─ 사용자 인증 (JWT)
   ├─ 공부 세션(Session) 데이터 관리
   └─ 이미지 파일 저장 및 URL 제공
            │
            ▼
[Android App]
   ├─ 로그인 & 대시보드
   ├─ 실시간 공부 시간 확인
   └─ "오늘의 공부 모습" 갤러리 뷰
   ```
   
---

## 🛠️ 기술 스택 (Tech Stack)

| 구분 | 기술 (Technology) | 설명 |
| :--- | :--- | :--- |
| **Edge AI** | **Python, YOLOv5** | COCO Pretrained 모델 활용, `Person` & `Book` 동시 감지 로직 구현 |
| **Backend** | **Django REST Framework** | 사용자 인증, 공부 세션 관리, 이미지 업로드 처리 API |
| **Database** | **SQLite** | 사용자 정보 및 시계열 공부 데이터 저장 |
| **Mobile** | **Android (Java)** | Retrofit2 통신, RecyclerView 갤러리, 통계 UI |

---

## 🚀 상세 기능 (Detailed Features)

### 1. 🧠 Edge (Object Detection)
* **실시간 감지:** 웹캠 피드에서 YOLOv5를 이용해 `Person` 객체와 `Book` 객체의 Bounding Box를 실시간 추적합니다.
* **로직 판별:** 두 객체가 일정 시간(예: 3초) 이상 동시에 존재할 때만 **STUDYING** 상태로 전환합니다.
* **자동 캡처:** 공부 시작 시점 및 일정 주기마다 프레임(Frame)을 캡처하여 서버로 전송합니다.

### 2. 🗄️ Server (Django API)
* **인증 (Auth):** JWT 기반의 `/auth/login` 처리를 통해 보안을 유지합니다.
* **세션 기록:** `/study/start`, `/study/end` 요청을 받아 정확한 공부 시간을 계산합니다.
* **이미지 처리:** Base64 혹은 Multipart로 전송된 이미지를 저장하고 `/image/upload` 엔드포인트를 관리합니다.
* **통계 제공:** 일간/주간 공부 시간 데이터를 JSON 형태로 앱에 전달합니다.

### 3. 📱 Android (User Interface)
* **대시보드:** 오늘 총 공부 시간과 현재 상태를 직관적으로 보여줍니다.
* **Study Gallery:** 서버에 저장된 캡처 이미지를 그리드 뷰(Grid View)로 나열하여 보여줍니다.
* **상세 보기:** 이미지를 클릭하면 전체 화면으로 확대되며, 기기에 저장할 수 있습니다.