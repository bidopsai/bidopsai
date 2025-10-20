/**
 * Password Reset Page - Disabled
 *
 * This page is disabled. Users should contact an administrator
 * if they need a password reset.
 */

'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function ResetPasswordPage() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to sign-in page immediately
    router.push('/signin?message=Password reset is disabled. Contact an administrator for assistance.');
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <p className="text-muted-foreground">Redirecting to sign in...</p>
      </div>
    </div>
  );
}
