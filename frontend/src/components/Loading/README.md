# Universal Loading UI System

Reusable loading components and skeletons for all HBSE platform pages.

## Components

### 1. **LoadingSpinner**
Animated loading spinner with optional message.

```tsx
import { LoadingSpinner } from '@/components/Loading';

<LoadingSpinner message="Loading your tutor..." size="md" />
<LoadingSpinner message="Please wait..." size="lg" fullScreen />
```

**Props:**
- `message?: string` — Loading message (default: "Loading...")
- `size?: 'sm' | 'md' | 'lg'` — Icon size (default: 'md')
- `fullScreen?: boolean` — Fill viewport (default: false)

---

### 2. **Skeleton Components**
Pre-built skeletons for different content types:

- `SkeletonPulse` — Basic pulse rectangle
- `ChatMessageSkeleton` — AI Tutor messages
- `DashboardCardSkeleton` — Dashboard stat cards
- `QuestionSkeleton` — Practice questions with options
- `FormFieldSkeleton` — Form inputs
- `TextSkeleton` — Paragraph text blocks
- `ChapterReaderSkeleton` — Chapter content layout

```tsx
import { ChatMessageSkeleton, QuestionSkeleton } from '@/components/Loading';

<ChatMessageSkeleton />
<QuestionSkeleton />
```

---

### 3. **Page-Specific Loading States**
Pre-composed loading screens for each page:

```tsx
import {
  TutorPageLoading,
  DashboardLoading,
  PracticeLoading,
  ProfileLoading,
  BadgesLoading,
  SettingsLoading,
} from '@/components/Loading';

{isLoading && <TutorPageLoading />}
```

---

### 4. **LoadingWrapper**
Conditional wrapper for loading/content/error states:

```tsx
import { LoadingWrapper, DashboardLoading } from '@/components/Loading';

<LoadingWrapper
  isLoading={isLoading}
  error={error}
  skeleton={<DashboardLoading />}
>
  <YourContent />
</LoadingWrapper>
```

**Props:**
- `isLoading: boolean` — Show skeleton state
- `error?: string` — Show error message
- `skeleton: ReactNode` — Loading content
- `children: ReactNode` — Main content

---

### 5. **usePageLoading Hook**
Manage loading state easily:

```tsx
import { usePageLoading } from '@/hooks/usePageLoading';

const { isLoading, message, setLoaded } = usePageLoading({
  initialMessage: 'Loading your practice questions...',
  timeout: 5000,
});

useEffect(() => {
  api.get('/questions').then(() => setLoaded());
}, []);
```

---

## Usage Examples

### Example 1: Tutor Page (Already Implemented)

```tsx
import { TutorPageLoading } from '@/components/Loading';

export default function TutorPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    api.get('/chat/history')
      .then((data) => {
        setHistory(data);
        setIsLoading(false);
      });
  }, []);

  return (
    <div>
      {isLoading && <TutorPageLoading />}
      {!isLoading && <ChatMessages history={history} />}
    </div>
  );
}
```

### Example 2: Dashboard (Already Implemented)

```tsx
import { DashboardLoading } from '@/components/Loading';

if (loading) {
  return <DashboardLoading />;
}
```

### Example 3: Practice Questions

```tsx
import { PracticeLoading, LoadingWrapper } from '@/components/Loading';

export default function PracticePage() {
  const [questions, setQuestions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/practice/questions')
      .then((data) => setQuestions(data))
      .catch((e) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <LoadingWrapper
      isLoading={isLoading}
      error={error}
      skeleton={<PracticeLoading />}
    >
      <QuestionsList questions={questions} />
    </LoadingWrapper>
  );
}
```

### Example 4: Profile Page

```tsx
import { ProfileLoading } from '@/components/Loading';

export default function ProfilePage() {
  const [profile, setProfile] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    api.get('/profile')
      .then((data) => {
        setProfile(data);
        setIsLoading(false);
      });
  }, []);

  if (isLoading) {
    return <ProfileLoading />;
  }

  return <ProfileForm profile={profile} />;
}
```

---

## Styling

All components use:
- **Color**: Teal accents (`bg-teal-600`, `text-teal-600`)
- **Animation**: Smooth pulse effect (`animate-pulse`)
- **Layout**: Flexbox + grid for responsive design
- **Typography**: Stone color scale for neutral tones

---

## Customization

To customize the look:

1. **Change colors** in `SkeletonBase.tsx`:
   ```tsx
   // Change from stone-200 to another color
   <div className="bg-your-color rounded animate-pulse" />
   ```

2. **Adjust timing** by modifying the `animate-pulse` class in `globals.css`

3. **Create custom skeleton variants**:
   ```tsx
   // Add to SkeletonBase.tsx
   export function YourCustomSkeleton() {
     return (
       <div className="space-y-2">
         <SkeletonPulse className="h-6 w-1/3" />
         <SkeletonPulse className="h-4 w-full" />
       </div>
     );
   }
   ```

---

## Pages Updated ✅

- ✅ AI Tutor (`/tutor`)
- ✅ Dashboard (`/dashboard`)
- ✅ Badges (`/badges`)
- 🔄 Practice Questions (to be added)
- 🔄 Profile (`/profile`)
- 🔄 Settings (`/settings`)
- 🔄 Chapter Reader (to be added)

---

## Best Practices

1. **Always show a skeleton** — Never show blank screen while loading
2. **Use context-aware messages** — "Loading your practice questions..."
3. **Set reasonable timeouts** — Warn users if loading takes > 5s
4. **Handle errors gracefully** — Always show error state
5. **Preload if possible** — Use skeleton placeholders immediately

---

## Performance Tips

- Skeletons are lightweight (~50 bytes each)
- Use `animate-pulse` for hardware-accelerated animations
- Consider lazy-loading images to reduce initial load
- Cache API responses when possible
