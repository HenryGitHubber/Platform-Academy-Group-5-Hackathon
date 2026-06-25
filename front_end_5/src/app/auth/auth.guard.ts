import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

export const authGuard: CanActivateFn = async () => {
  if (typeof window === 'undefined') {
    return true;
  }

  const authService = inject(AuthService);
  const router = inject(Router);
  const isAuthenticated = await authService.isAuthenticated();

  return isAuthenticated ? true : router.createUrlTree(['/login']);
};