export type PageType = 
  | 'tutor' 
  | 'dashboard' 
  | 'practice' 
  | 'profile' 
  | 'settings' 
  | 'default';

interface LoadingStep {
  id: number;
  label: string;
  duration: number;
}

interface LoadingConfig {
  steps: LoadingStep[];
  microCopy: string[];
  pageTitle: string;
  emoji: string;
}

const configs: Record<PageType, LoadingConfig> = {
  tutor: {
    pageTitle: 'AI Tutor is getting ready',
    emoji: '',
    steps: [
      { id: 1, label: 'Authenticating your session', duration: 600 },
      { id: 2, label: 'Loading your profile', duration: 900 },
      { id: 3, label: 'Preparing subject content', duration: 1200 },
      { id: 4, label: 'Starting AI Tutor', duration: 800 },
    ],
    microCopy: [
      'Preparing your personalized lesson...',
      'Fetching Class 9 content from HBSE curriculum...',
      'Your AI Tutor is almost ready...',
      'Loading practice questions for you...',
      'Connecting to your learning profile...',
      'Almost there — let\'s learn something great today!',
    ],
  },

  dashboard: {
    pageTitle: 'Loading your dashboard',
    emoji: '',
    steps: [
      { id: 1, label: 'Authenticating your session', duration: 600 },
      { id: 2, label: 'Fetching your progress', duration: 1000 },
      { id: 3, label: 'Loading recommendations', duration: 1100 },
      { id: 4, label: 'Preparing your dashboard', duration: 700 },
    ],
    microCopy: [
      'Gathering your learning stats...',
      'Calculating your progress across all subjects...',
      'Building your personalized dashboard...',
      'Finding new topics to explore...',
      'Loading your recent activity...',
      'Your dashboard is ready!',
    ],
  },

  practice: {
    pageTitle: 'Practice questions loading',
    emoji: '',
    steps: [
      { id: 1, label: 'Authenticating your session', duration: 600 },
      { id: 2, label: 'Loading question bank', duration: 1000 },
      { id: 3, label: 'Selecting questions for your level', duration: 1200 },
      { id: 4, label: 'Preparing practice test', duration: 800 },
    ],
    microCopy: [
      'Picking questions matched to your level...',
      'Loading previous year board exam questions...',
      'Preparing MCQs and short answers...',
      'Setting up the practice timer...',
      'Your practice test is ready...',
      'Let\'s test your knowledge!',
    ],
  },

  profile: {
    pageTitle: 'Loading your profile',
    emoji: '',
    steps: [
      { id: 1, label: 'Authenticating your session', duration: 600 },
      { id: 2, label: 'Fetching your profile data', duration: 900 },
      { id: 3, label: 'Loading your certificates', duration: 1000 },
      { id: 4, label: 'Preparing your profile', duration: 700 },
    ],
    microCopy: [
      'Loading your learning journey...',
      'Fetching your badges and certificates...',
      'Calculating your achievement stats...',
      'Preparing your profile overview...',
      'Your profile is ready to view!',
    ],
  },

  settings: {
    pageTitle: 'Loading settings',
    emoji: '',
    steps: [
      { id: 1, label: 'Authenticating your session', duration: 600 },
      { id: 2, label: 'Fetching your preferences', duration: 800 },
      { id: 3, label: 'Loading notification settings', duration: 900 },
      { id: 4, label: 'Preparing settings', duration: 600 },
    ],
    microCopy: [
      'Loading your preferences...',
      'Fetching language and theme settings...',
      'Preparing notification options...',
      'Getting your account settings...',
      'Settings ready to customize!',
    ],
  },

  default: {
    pageTitle: 'Loading page',
    emoji: '',
    steps: [
      { id: 1, label: 'Authenticating your session', duration: 600 },
      { id: 2, label: 'Loading data', duration: 900 },
      { id: 3, label: 'Preparing content', duration: 1000 },
      { id: 4, label: 'Ready', duration: 700 },
    ],
    microCopy: [
      'Just a moment...',
      'Loading your content...',
      'Almost there...',
      'Getting everything ready...',
    ],
  },
};

export function useLoadingConfig(pageType: PageType): LoadingConfig {
  return configs[pageType] || configs.default;
}
