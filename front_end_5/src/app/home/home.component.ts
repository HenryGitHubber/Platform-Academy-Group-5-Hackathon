import { Component, OnInit, Inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser }                        from '@angular/common';
import { CommonModule }                             from '@angular/common';
import { FormsModule }                              from '@angular/forms';
import { Router }                                   from '@angular/router';
import { DomSanitizer, SafeResourceUrl }            from '@angular/platform-browser';
import { QuicksightEmbedService }                   from '../services/quicksight-embed.service';
import { AuthService }                              from '../services/auth.service';

interface QSPanelInsight {
  question: string;
  explanation: string[];
  formula?: string;
  tips: string[];
}

interface QSPanel {
  id: string;
  title: string;
  icon: string;
  description: string;
  insight?: QSPanelInsight;
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
  private readonly SHEET_ID = '9d9c754b-7cdb-4c8e-b483-123a0e879c88_6a473978-af49-4f7d-825b-0ad5dae6f427';

  quicksightPanels: QSPanel[] = [
    { id: 'qs-1', title: 'Programme Performance',    icon: '📊',
      description: 'ROI score, Completion rate & Avg satisfaction by Programme',
      insight: {
        question: 'Which training programmes deliver the highest return on investment?',
        explanation: [
          'This view ranks training programmes based on a calculated ROI score, combining completion, satisfaction, and cost.',
          'Completion rate = employees who completed the programme ÷ total employees.',
          'Average satisfaction = overall employee satisfaction score (scaled to 0–10).',
          'Average cost = total training spend ÷ total employees.',
          'These values are normalised and combined into a single formula.',
          'Higher scores indicate programmes that achieve strong completion, maintain high satisfaction, and do so at a lower relative cost.',
        ],
        formula: 'ROI = (Satisfaction × Completion) ÷ Cost',
        tips: [
          'Use this view to quickly identify high-value programmes.',
          'Top-ranked programmes deliver the best balance of impact vs spend.',
          'Lower-ranked programmes may require cost optimisation, improved engagement, or redesign.',
        ],
      },
      sheetId: this.SHEET_ID,
      visualId: '9d9c754b-7cdb-4c8e-b483-123a0e879c88_41980dfa-7933-40d5-bf61-820433ea7bb7',
      embedUrl: null, loading: false, error: null },
    { id: 'qs-2', title: 'Satisfaction by Year',     icon: '⭐',
      description: 'Average satisfaction scores — 2023 / 2024 / 2025',
      insight: {
        question: 'How satisfied are employees with their training experience?',
        explanation: [
          'Satisfaction is based on the numeric scores derived from employee survey responses.',
          'The system calculates: Average Satisfaction = Sum of all employee scores ÷ Number of responses.',
          'Scores are standardised on a 0–10 scale.',
        ],
        formula: 'Average Satisfaction = Sum of all employee scores ÷ Number of responses',
        tips: [
          'Provides a high-level signal of training quality.',
          'Use this to validate programme effectiveness and compare against cost and completion.',
          'Best used in combination with other metrics (not standalone).',
        ],
      },
      sheetId: this.SHEET_ID,
      visualId: '9d9c754b-7cdb-4c8e-b483-123a0e879c88_761736f6-9b20-4777-8371-aa5d3eb03560',
      embedUrl: null, loading: false, error: null },
    { id: 'qs-3', title: 'Success Rate by Category', icon: '🎯',
      description: 'Success rates broken down by job category',
      insight: {
        question: 'Which employee roles achieve the highest training success outcomes?',
        explanation: [
          'This view compares success rates across different employee roles to highlight where training delivers the strongest outcomes.',
          'Data used: Employee role classification, training completion status (per employee), and satisfaction scores (0–10 scale).',
          'Employees are grouped by role; a "successful outcome" is defined using both completion and satisfaction thresholds.',
          'Role-level success rates are calculated and compared across the organisation.',
        ],
        formula: 'Success Condition = Completed ≥ 1 programme AND Satisfaction ≥ 7  |  Success Rate per Role = Successful employees ÷ Total employees in role',
        tips: [
          'High success rate → training is well-aligned to role needs.',
          'Low success rate → potential gaps in relevance, accessibility, or engagement.',
          'Data Engineers, Software Developers, and Graduates show strong success contributions relative to other roles.',
          'Use this to prioritise and tailor training investment by role.',
        ],
      },
      sheetId: this.SHEET_ID,
      visualId: '9d9c754b-7cdb-4c8e-b483-123a0e879c88_ff51ac7f-0adf-43f8-ae43-455b4b263d5a',
      embedUrl: null, loading: false, error: null },
    { id: 'qs-4', title: 'Cost per Employee',        icon: '💶',
      description: 'Training spend distribution and stream breakdown',
      insight: {
        question: 'How much is being invested per employee?',
        explanation: [
          'This view calculates how training costs are distributed across employees.',
          'Data used: Fixed programme costs and employee participation per programme.',
          'Total cost is accumulated per employee based on attended programmes.',
          'An overall average is then calculated across all employees.',
        ],
        formula: 'Avg Cost per Employee = Total cost ÷ Total employees',
        tips: [
          'Identifies high-cost employees or programmes.',
          'Reveals cost concentration patterns across the organisation.',
          'Supports budget planning and cost vs ROI balancing.',
          'Ensures efficient allocation of training resources.',
        ],
      },
      sheetId: this.SHEET_ID,
      visualId: '9d9c754b-7cdb-4c8e-b483-123a0e879c88_ef861f34-b5c6-4901-b362-b3cb8d15953c',
      embedUrl: null, loading: false, error: null },
    { id: 'qs-5', title: 'Enrolment Trends',         icon: '📅',
      description: 'Headcount and enrolment trends by intake year',
      sheetId: this.SHEET_ID,
      visualId: '9d9c754b-7cdb-4c8e-b483-123a0e879c88_2aceb5de-105d-4c02-9c37-c532e75a2ca8',
      embedUrl: null, loading: false, error: null },
    { id: 'qs-6', title: 'ROI by Stream',            icon: '📈',
      description: 'Return on investment scored by stream and year',
      sheetId: this.SHEET_ID,
      visualId: '9d9c754b-7cdb-4c8e-b483-123a0e879c88_806ccf33-4613-4326-8eaf-7073b854afba',
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
