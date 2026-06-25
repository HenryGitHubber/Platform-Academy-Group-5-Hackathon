import { Injectable } from '@angular/core';
import { Amplify } from 'aws-amplify';
import { getCurrentUser, signIn, signOut } from 'aws-amplify/auth';
import { cognitoConfig, isCognitoConfigured } from '../auth/cognito.config';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private configured = false;

  constructor() {
    this.configure();
  }

  async login(username: string, password: string) {
    if (!username || !password) {
      throw new Error('Username and password are required.');
    }

    this.configure();
    const result = await signIn({
      username,
      password,
    });

    if (!result.isSignedIn) {
      const step = result.nextStep?.signInStep ?? 'UNKNOWN';
      throw new Error(`Cognito requires an additional sign-in step: ${step}.`);
    }
  }

  async logout() {
    this.configure();
    await signOut();
  }

  async isAuthenticated(): Promise<boolean> {
    if (typeof window === 'undefined') {
      return false;
    }

    this.configure();

    try {
      await getCurrentUser();
      return true;
    } catch {
      return false;
    }
  }

  private configure() {
    if (this.configured || typeof window === 'undefined') {
      return;
    }

    if (!isCognitoConfigured()) {
      throw new Error('Cognito is not configured. Update src/app/auth/cognito.config.ts with your region, user pool ID, and app client ID.');
    }

    Amplify.configure({
      Auth: {
        Cognito: {
          userPoolId: cognitoConfig.userPoolId,
          userPoolClientId: cognitoConfig.userPoolClientId,
        },
      },
    });

    this.configured = true;
  }
}
