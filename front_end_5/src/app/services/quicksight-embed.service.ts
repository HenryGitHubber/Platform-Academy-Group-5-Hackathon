import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

export interface QSVisual {
  visualId: string;
  title: string;
  type: string;
}

export interface QSSheet {
  sheetId: string;
  sheetName: string;
  visuals: QSVisual[];
}

@Injectable({ providedIn: 'root' })
export class QuicksightEmbedService {
  private readonly proxyUrl = 'http://localhost:3001';

  constructor(private http: HttpClient) {}

  private async call<T>(path: string): Promise<T> {
    const result = await firstValueFrom(
      this.http.get<T & { error?: string; code?: string }>(this.proxyUrl + path)
    );
    if ((result as any).error) {
      throw new Error(`${(result as any).code ?? 'Error'}: ${(result as any).error}`);
    }
    return result;
  }

  /** Q Search Bar embed URL */
  async getQSearchBarUrl(): Promise<string> {
    const r = await this.call<{ url: string }>('/embed-url');
    return r.url;
  }

  /** Full dashboard embed URL */
  async getDashboardEmbedUrl(dashboardId?: string): Promise<string> {
    const qs = dashboardId ? `?dashboardId=${dashboardId}` : '';
    const r = await this.call<{ url: string }>(`/embed-dashboard${qs}`);
    return r.url;
  }

  /** Single visual embed URL */
  async getVisualEmbedUrl(sheetId: string, visualId: string, dashboardId?: string): Promise<string> {
    const base = dashboardId || '';
    const qs = `?sheetId=${encodeURIComponent(sheetId)}&visualId=${encodeURIComponent(visualId)}`
             + (base ? `&dashboardId=${base}` : '');
    const r = await this.call<{ url: string }>(`/embed-visual${qs}`);
    return r.url;
  }

  /** Describe dashboard — returns all sheets + visual IDs */
  async getDashboardVisuals(dashboardId?: string): Promise<{ dashboardId: string; sheets: QSSheet[] }> {
    const qs = dashboardId ? `?dashboardId=${dashboardId}` : '';
    return this.call(`/describe-dashboard${qs}`);
  }

  /** @deprecated kept for backwards compatibility */
  async getEmbedUrl(): Promise<string> { return this.getQSearchBarUrl(); }
}
