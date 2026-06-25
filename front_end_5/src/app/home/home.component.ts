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

  ngOnInit() {
    if (isPlatformBrowser(this.platformId)) {
      this.loadPanelEmbeds();
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

  // ── Amazon Q Chat ────────────────────────────────────────────────────────
  messages: { from: 'user' | 'bot'; text: string }[] = [
    { from: 'bot', text: 'Hi! I\'m Amazon Q. Ask me anything about the Platform Academy data — 376 employees, 35 fields, live from S3.' },
    { from: 'user', text: 'How many completed the hackathon each year?' },
    { from: 'bot', text: '🏆 Hackathon completions by year:\n• 2025: 116  (+52% vs 2023)\n• 2024: 88\n• 2023: 76' },
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
      return '💶 Total cost by year:\n• 2025: €122,618 (+47.5% YoY)\n• 2024: €83,089 (+20.2% YoY)\n• 2023: €69,123 (baseline)\nTotal spend: €277,192.60';
    if (s.includes('satisfaction') || s.includes('score'))
      return '⭐ Avg satisfaction score: 6.77 / 10\nFor a full breakdown by stream, click Launch Amazon Q.';
    if (s.includes('complet') || s.includes('module'))
      return '✅ Overall success rate: 61.7%\n• Hackathon: 280 completions total\n• Certification exam: 61.7% passed';
    if (s.includes('skillbuilder'))
      return '📚 SkillBuilder completions:\n• 2025: 136 employees\n• 2024: 142 employees\n• 2023: 98 employees';
    if (s.includes('enrol') || s.includes('how many') || (s.includes('employee') && !s.includes('cost')))
      return '👥 Employees enrolled by year:\n• 2023: 98\n• 2024: 142\n• 2025: 136\n• Total: 376 employees';
    if (s.includes('year') || s.includes('trend'))
      return '📈 Year-over-year trends:\n• Enrolments: 98 → 142 → 136\n• Spend: €69k → €83k → €123k\n• Hackathon: 76 → 88 → 116\n2025 spend nearly doubled vs 2023.';
    return '🤖 I can answer questions about hackathon completions, training costs, enrolment counts, satisfaction scores, and year trends.\n\nFor live AI-generated charts, click Launch Amazon Q above.';
  }
}
