# 📱 QuantSight Mobile App Deployment Guide

This guide walks you through deploying the QuantSight frontend as a mobile application.

---

## 🎯 Deployment Options

### Option A: React Native (Recommended for Native Experience)

**Best for**: Native iOS/Android apps with best performance

### Option B: Progressive Web App (PWA)

**Best for**: Quick deployment, no app store approval needed

### Option C: Expo (Fastest Setup)

**Best for**: Rapid development with over-the-air updates

---

## Option A: React Native (Native Apps)

### Prerequisites

- Node.js 18+
- For iOS: MacOS with Xcode 14+
- For Android: Android Studio with SDK 33+
- React Native CLI: `npm install -g react-native-cli`

### Step 1: Create New React Native Project

```bash
npx react-native init QuantSightMobile --template react-native-template-typescript
cd QuantSightMobile
```

### Step 2: Copy Core Components

Copy these directories from `quantsight_cloud_build/src` to your new project's `src/`:

- `components/`
- `hooks/`
- `services/`
- `config/`

### Step 3: Update API Configuration

The `src/config/apiConfig.ts` is already configured to:

- Detect mobile devices automatically
- Use Cloud Run backend: `https://quantsight-cloud-458498663186.us-central1.run.app`

### Step 4: Install Dependencies

```bash
npm install react-native-reanimated react-native-safe-area-context
npm install @react-navigation/native @react-navigation/native-stack
npm install victory-native
npm install nativewind
```

### Step 5: Build and Run

**iOS:**

```bash
cd ios && pod install && cd ..
npx react-native run-ios
```

**Android:**

```bash
npx react-native run-android
```

---

## Option B: Progressive Web App (PWA)

### Step 1: Build Production Bundle

```bash
cd quantsight_cloud_build
npm install
npm run build
```

### Step 2: Deploy to Firebase Hosting

```bash
npm install -g firebase-tools
firebase login
firebase init hosting
# Select: quantsight-prod
# Public directory: dist
# Single-page app: Yes
firebase deploy
```

**Your PWA will be live at**: `https://quantsight-prod.web.app`

### Step 3: Add to Home Screen

Users can add the PWA to their phone's home screen:

- **iOS**: Safari → Share → Add to Home Screen
- **Android**: Chrome → Menu → Add to Home Screen

---

## Option C: Expo (Fastest Deployment)

### Step 1: Create Expo Project

```bash
npx create-expo-app QuantSightExpo --template expo-template-blank-typescript
cd QuantSightExpo
```

### Step 2: Install Dependencies

```bash
npx expo install react-native-reanimated react-native-safe-area-context
npx expo install victory-native
```

### Step 3: Copy Source Files

Copy from `quantsight_cloud_build/src/`:

- `config/apiConfig.ts`
- `services/nexusApi.ts`
- `components/` (convert web-specific styles to React Native)

### Step 4: Run Development

```bash
npx expo start
```

Scan QR code with Expo Go app on your phone.

### Step 5: Build for Production

```bash
# iOS
eas build --platform ios

# Android
eas build --platform android
```

---

## 🔌 API Integration

Your mobile app connects to:

**Production API**: `https://quantsight-cloud-458498663186.us-central1.run.app`

### Available Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /status` | Detailed status |
| `GET /admin/db-status` | Database status |

### Firebase Real-time (Optional)

For real-time updates, connect to Firebase:

```javascript
import { initializeApp } from 'firebase/app';
import { getFirestore, collection, onSnapshot } from 'firebase/firestore';

const firebaseConfig = {
  projectId: 'quantsight-prod',
  // Add other config from Firebase Console
};

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

// Listen to live games
onSnapshot(collection(db, 'live_games'), (snapshot) => {
  snapshot.docChanges().forEach((change) => {
    console.log('Game updated:', change.doc.data());
  });
});
```

---

## 📊 Testing Your Setup

### Verify Backend Connection

```javascript
fetch('https://quantsight-cloud-458498663186.us-central1.run.app/health')
  .then(res => res.json())
  .then(data => console.log('Backend status:', data));
```

### Expected Response

```json
{
  "status": "healthy",
  "database_url_set": true,
  "producer": {
    "running": true,
    "firebase_enabled": true
  }
}
```

---

## 🚀 App Store Deployment

### iOS App Store

1. Create App Store Connect account
2. Configure signing in Xcode
3. Archive and upload via Xcode
4. Submit for review

### Google Play Store

1. Create Google Play Console account
2. Generate signed APK/AAB
3. Upload to Play Console
4. Submit for review

---

## 📝 Quick Start Summary

| Method | Setup Time | Performance | App Store Required |
|--------|-----------|-------------|-------------------|
| React Native | 2-4 hours | Excellent | Yes |
| PWA | 30 min | Good | No |
| Expo | 1-2 hours | Very Good | Optional |

**Recommended Path**:

1. Start with **PWA** for immediate deployment
2. Build **Expo** version for beta testing
3. Graduate to **React Native** for production

---

## 🔗 Related Resources

- [React Native Docs](https://reactnative.dev/docs/getting-started)
- [Expo Docs](https://docs.expo.dev/)
- [Firebase Hosting](https://firebase.google.com/docs/hosting)
- [Cloud Run API](https://quantsight-cloud-458498663186.us-central1.run.app/health)
