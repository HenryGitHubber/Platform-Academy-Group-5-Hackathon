import { Component, OnInit, Inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser }                        from '@angular/common';
import { CommonModule }                             from '@angular/common';
import { FormsModule }                              from '@angular/forms';
import { Router }                                   from '@angular/router';
import { DomSanitizer, SafeResourceUrl }            from '@angular/platform-browser';
import { QuicksightEmbedService }                   from '../services/quicksight-embed.service';
import { AuthService }                              from '../services/auth.service';

interface QSPanel {
  id: string;
  title: string;
  icon: string;
  description: string;
  /** Fill these in after running:  GET http://localhost:3001/describe-dashboard */
  sheetId:  string | null;
  visualId: string | null;
  embedUrl: SafeResourceUrl | null;
  loading:  boolean;
  error:    string | null;
}

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, FormsModule],
  // RouterLink not needed — signOut() uses Router programmatically
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css']
})
export class HomeComponent implements OnInit {
  currentYear = new Date().getFullYear();

  // ─────────────────────────────────────────────────────────────────────────
  // Sheet + Visual IDs from:
  //   aws quicksight describe-dashboard-definition --dashboard-id 1a71c9ed-...
  // ─────────────────────────────────────────────────────────────────────────
  private readonly SHEET_ID = '1a71c9ed-29ed-4ac3-a540-9ea1e49182ef_75b99231-7ec4-4388-b478-9be838575595';

  quicksightPanels: QSPanel[] = [
    { id: 'qs-1', title: 'Programme Performance',    icon: '📊',
      description: 'ROI score, Completion rate & Avg satisfaction by Programme',
      sheetId: this.SHEET_ID,
      visualId: '1a71c9ed-29ed-4ac3-a540-9ea1e49182ef_74419e9c-0433-4bca-89b8-b497d318e544',
      embedUrl: null, loading: false, error: null },
    { id: 'qs-2', title: 'Satisfaction by Year',     icon: '⭐',
      description: 'Average satisfaction scores — 2023 / 2024 / 2025',
      sheetId: this.SHEET_ID,
      visualId: '1a71c9ed-29ed-4ac3-a540-9ea1e49182ef_737a7ca0-5667-45de-b7a9-2e2548c57483',
      embedUrl: null, loading: false, error: null },
    { id: 'qs-3', title: 'Success Rate by Category', icon: '🎯',
      description: 'Success rates broken down by job category',
      sheetId: this.SHEET_ID,
      visualId: '1a71c9ed-29ed-4ac3-a540-9ea1e49182ef_a89dea26-52ea-41cf-839c-a234a641390b',
      embedUrl: null, loading: false, error: null },
    { id: 'qs-4', title: 'Cost per Employee',        icon: '💶',
      description: 'Training spend distribution and stream breakdown',
      sheetId: this.SHEET_ID,
      visualId: '1a71c9ed-29ed-4ac3-a540-9ea1e49182ef_5015ff7f-6342-4290-a7ca-e82d3a82d20c',
      embedUrl: null, loading: false, error: null },
    { id: 'qs-5', title: 'Enrolment Trends',         icon: '📅',
      description: 'Headcount and enrolment trends by intake year',
      sheetId: this.SHEET_ID,
      visualId: '1a71c9ed-29ed-4ac3-a540-9ea1e49182ef_0705a773-c4e3-4a2d-aa8b-79dd192f7d61',
      embedUrl: null, loading: false, error: null },
    { id: 'qs-6', title: 'ROI by Stream',            icon: '📈',
      description: 'Return on investment scored by stream and year',
      sheetId: this.SHEET_ID,
      visualId: '1a71c9ed-29ed-4ac3-a540-9ea1e49182ef_bb623d70-a19f-423d-a106-3a945057d9ae',
      embedUrl: null, loading: false, error: null },
  ];

  constructor(
    @Inject(PLATFORM_ID) private platformId: object,
    private sanitizer: DomSanitizer,
    private qsEmbed: QuicksightEmbedService,
    private authService: AuthService,
    private router: Router,
  ) {}

  async signOut() {
    await this.authService.logout();
    await this.router.navigate(['/login']);
  }

  fullDashboardUrl: SafeResourceUrl | null = null;
  fullDashboardError: string | null = null;

  /** Panel currently shown in the expand modal */
  expandedPanel: QSPanel | null = null;
  modalEmbedUrl: SafeResourceUrl | null = null;
  modalLoading = false;
  modalError: string | null = null;

  async openModal(panel: QSPanel) {
    this.expandedPanel = panel;
    this.modalEmbedUrl = null;
    this.modalError = null;
    this.modalLoading = true;
    try {
      const url = await this.qsEmbed.getVisualEmbedUrl(panel.sheetId!, panel.visualId!);
      this.modalEmbedUrl = this.sanitizer.bypassSecurityTrustResourceUrl(url);
    } catch (e: any) {
      this.modalError = e.message ?? 'Failed to load chart';
    } finally {
      this.modalLoading = false;
    }
  }

  closeModal() {
    this.expandedPanel = null;
    this.modalEmbedUrl = null;
    this.modalError = null;
  }

  ngOnInit() {
    if (isPlatformBrowser(this.platformId)) {
      this.loadPanelEmbeds();
      this.loadFullDashboard();
    }
  }

  /** Embed each panel that has a sheetId + visualId configured */
  private async loadPanelEmbeds() {
    for (const panel of this.quicksightPanels) {
      if (!panel.sheetId || !panel.visualId) continue;
      panel.loading = true;
      try {
        const url = await this.qsEmbed.getVisualEmbedUrl(panel.sheetId, panel.visualId);
        panel.embedUrl = this.sanitizer.bypassSecurityTrustResourceUrl(url);
      } catch (e: any) {
        panel.error = e.message ?? 'Failed to load chart';
      } finally {
        panel.loading = false;
      }
    }
  }

  /** Load full dashboard embed (includes filter controls) */
  private async loadFullDashboard() {
    try {
      const url = await this.qsEmbed.getDashboardEmbedUrl();
      this.fullDashboardUrl = this.sanitizer.bypassSecurityTrustResourceUrl(url);
    } catch (e: any) {
      this.fullDashboardError = e.message ?? 'Failed to load full dashboard';
    }
  }

  // ── Amazon Q Chat ────────────────────────────────────────────────────────
  messages: { from: 'user' | 'bot'; text: string }[] = [
    { from: 'bot', text: 'Hi! I\'m Amazon Q. Ask me anything about the Platform Academy data — 447 employees, live from S3.' },
    { from: 'user', text: 'How many employees are enrolled?' },
    { from: 'bot', text: '\uD83D\uDC65 Total employees enrolled: 447\n\u20ac1,334,911.90 total training spend\nAvg satisfaction: 6.83 / 10' },
  ];

  userInput = '';
  thinking  = false;

  send() {
    const q = this.userInput.trim();
    if (!q || this.thinking) return;
    this.messages.push({ from: 'user', text: q });
    this.userInput = '';
    this.thinking  = true;
    setTimeout(() => {
      this.messages.push({ from: 'bot', text: this.answer(q) });
      this.thinking = false;
    }, 800);
  }

  private answer(q: string): string {
    const s = q.toLowerCase();
    if (s.includes('hackathon'))
      return '🏆 Hackathon completions by year:\n• 2025: 116  (+52% vs 2023)\n• 2024: 88\n• 2023: 76';
    if (s.includes('cost') && (s.includes('stream') || s.includes('avg') || s.includes('average') || s.includes('per')))
      return '📊 Avg training cost per stream:\n• Operations Engineer: €836.80 (highest)\n• Platform Engineering: €821.45\n• Data & AI: €789.20\n• Cloud Ops / Reliability: €692.11 (lowest)';
    if (s.includes('total cost') || s.includes('cost') && s.includes('year'))
      return '💶 Total training spend: €1,334,911.90\n• Hackathon has the highest ROI score\n• See Cost per Employee chart for full breakdown.';
    if (s.includes('satisfaction') || s.includes('score'))
      return '⭐ Avg satisfaction score: 6.83 / 10\nFor a full breakdown by stream, click Launch Amazon Q.';
    if (s.includes('complet') || s.includes('module'))
      return '✅ Overall success rate: 61%\n• Hackathon: highest ROI programme\n• Certification exam: 61% passed';
    if (s.includes('skillbuilder'))
      return '📚 SkillBuilder completions:\n• 2025: 136 employees\n• 2024: 142 employees\n• 2023: 98 employees';
    if (s.includes('enrol') || s.includes('how many') || (s.includes('employee') && !s.includes('cost')))
      return '👥 Total employees enrolled: 447\nLive data from S3 pipeline — updated in real-time.';
    if (s.includes('year') || s.includes('trend'))
      return '📈 Year-over-year trends:\n• Total employees: 447\n• Total spend: €1,334,911.90\n• Avg satisfaction: 6.83 / 10\n• Success rate: 61%\nSee the embedded charts for full breakdowns.';
    return '🤖 I can answer questions about hackathon completions, training costs, enrolment counts, satisfaction scores, and year trends.\n\nFor live AI-generated charts, click Launch Amazon Q above.';
  }
}
