/**
 * Sign In Form Component
 *
 * Provides username/password authentication with Google OAuth option.
 * Integrates with AWS Cognito through useAuth hook.
 */

'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useForm, type FieldErrors } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useSignIn } from '@/hooks/useAuth';
import { signInWithGoogle, getCurrentUser } from '@/lib/auth/cognito';
import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import styles from './AuthForms.module.css';
import { Loader2 } from 'lucide-react';

/**
 * Form validation schema
 */
const signInSchema = z.object({
  username: z.string().min(3, 'Username must be at least 3 characters'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});

type SignInFormValues = z.infer<typeof signInSchema>;

/**
 * Sign In Form Props
 */
interface SignInFormProps {
  /** Callback fired on successful sign in */
  onSuccess?: () => void;
}

export function SignInForm({ onSuccess }: SignInFormProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams?.get('redirect') || '/dashboard';

  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  const signInMutation = useSignIn();

  /**
   * Check if user is already authenticated on component mount
   * This follows AWS Amplify best practices
   */
  useEffect(() => {
    async function checkExistingAuth() {
      try {
        const user = await getCurrentUser();
        if (user) {
          console.log('✅ User already authenticated, redirecting to:', redirectTo);
          router.push(redirectTo);
        }
      } catch {
        // User not authenticated, show sign-in form
        console.log('No existing session, showing sign-in form');
      } finally {
        setIsCheckingAuth(false);
      }
    }

    checkExistingAuth();
  }, [router, redirectTo]);

  const form = useForm<SignInFormValues>({
    resolver: zodResolver(signInSchema),
    mode: 'onSubmit',
    reValidateMode: 'onChange',
    defaultValues: {
      username: '',
      password: '',
    },
  });

  /**
   * Handle form submission
   */
  async function onSubmit(values: SignInFormValues) {
    try {
      console.log('🔐 Sign in form submitted:', { username: values.username });
      console.log('📞 Calling signInMutation.mutate...');

      signInMutation.mutate(values, {
        onSuccess: (result) => {
          console.log('✅ Sign in result:', result);
          if (result.isSignedIn) {
            console.log('🎉 User is signed in! Redirecting to:', redirectTo);
            // Call success callback if provided
            onSuccess?.();

            // Redirect to target page
            router.push(redirectTo);
          } else {
            console.log('⏳ Sign in not complete, next step:', result.nextStep);
          }
          // If not signed in, nextStep is handled by useSignIn hook (toast messages)
        },
        onError: (error) => {
          console.error('❌ Sign in mutation error:', error);
        },
      });

      console.log('📤 Mutation triggered, waiting for response...');
    } catch (error) {
      // Form validation errors are handled by React Hook Form
      console.error('❌ Form submission error:', error);
    }
  }

  /**
   * Handle form errors
   */
  function onError(errors: FieldErrors<SignInFormValues>) {
    console.log('Form validation errors:', errors);
    // Errors will be displayed by FormMessage components
  }

  /**
   * Handle Google OAuth sign in
   */
  async function handleGoogleSignIn() {
    try {
      setIsGoogleLoading(true);
      await signInWithGoogle();
      // User will be redirected to Google OAuth
    } catch {
      setIsGoogleLoading(false);
      // Error is handled by cognito.ts
    }
  }

  const isLoading = signInMutation.isPending || isGoogleLoading || isCheckingAuth;

  // Show loading state while checking existing authentication
  if (isCheckingAuth) {
    return (
      <div className="w-full space-y-6">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="w-full space-y-6">
      {/* Header */}
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-bold tracking-tight">Welcome back</h1>
        <p className="text-muted-foreground">
          Sign in to your account to continue
        </p>
      </div>

      {/* Google Sign In */}
      <Button
        type="button"
        variant="outline"
        className="w-full"
        onClick={handleGoogleSignIn}
        disabled={isLoading}
      >
        {isGoogleLoading ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
            <path
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              fill="#4285F4"
            />
            <path
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              fill="#34A853"
            />
            <path
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              fill="#FBBC05"
            />
            <path
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              fill="#EA4335"
            />
          </svg>
        )}
        Continue with Google
      </Button>

      {/* Divider */}
      <div className={styles.divider}>
        <span>Or continue with</span>
      </div>

      {/* Username/Password Form */}
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit, onError)}
          className={`${styles.form} space-y-4`}
        >
          <FormField
            control={form.control}
            name="username"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Username or Email</FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    placeholder="Enter your username"
                    autoComplete="username"
                    disabled={isLoading}
                  />
                </FormControl>
                <FormMessage className={styles.error} />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Password</FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    type="password"
                    placeholder="Enter your password"
                    autoComplete="current-password"
                    disabled={isLoading}
                  />
                </FormControl>
                <FormMessage className={styles.error} />
              </FormItem>
            )}
          />

          <Button
            type="submit"
            className={`${styles.submit} w-full`}
            disabled={isLoading}
          >
            {signInMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Sign In
          </Button>
        </form>
      </Form>

      {/* Sign Up Link */}
      <div className="text-center text-sm">
        <span className="text-muted-foreground">Don&apos;t have an account? </span>
        <Link
          href="/signup"
          className="font-medium text-primary hover:underline"
        >
          Sign up
        </Link>
      </div>
    </div>
  );
}
