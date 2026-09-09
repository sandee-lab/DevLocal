import { useAppStore } from "../store/useAppStore";
import { getDownloadUrl } from "../api/client";
import { STAGGER, staggerDelay } from "../utils/stagger";
import Footer from "../components/Footer";

export default function DoneScreen() {
  const sessionId = useAppStore((s) => s.sessionId);
  const translationsApplied = useAppStore((s) => s.translationsApplied);
  const isWritingToSheet = useAppStore((s) => s.isWritingToSheet);
  const costSummary = useAppStore((s) => s.costSummary);
  const totalRows = useAppStore((s) => s.totalRows);
  const cellsUpdated = useAppStore((s) => s.cellsUpdated);
  const reviewResults = useAppStore((s) => s.reviewResults);
  const reset = useAppStore((s) => s.reset);

  const totalTokens = costSummary
    ? costSummary.input_tokens + costSummary.output_tokens + (costSummary.reasoning_tokens ?? 0)
    : 0;
  const cachedTokens = costSummary?.cached_tokens ?? 0;
  const reasoningTokens = costSummary?.reasoning_tokens ?? 0;
  const estimatedCost = costSummary?.estimated_cost_usd ?? 0;
  const failedRows = useAppStore((s) => s.failedRows);
  const langCount = new Set(reviewResults.map((r) => r.lang)).size;

  return (
    <>
      <main className="flex-1 flex flex-col py-12 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto w-full animate-celebrate">
        {/* Title */}
        <div className={`w-full mb-10 text-center ${STAGGER}`} style={staggerDelay(0)}>
          <h1 className="text-3xl font-bold text-text-main tracking-tight mb-3">
            Final Review & Push
          </h1>
          <p className="text-text-muted max-w-2xl mx-auto">
            Review the translation summary below before pushing changes to your
            Google Sheet.
          </p>
        </div>

        <div className="w-full space-y-8">
          {/* Success card */}
          <div className={`bg-gradient-to-br from-white to-sky-50 rounded-2xl p-8 border border-primary/20 shadow-soft relative overflow-hidden ${STAGGER}`} style={staggerDelay(1)}>
            <div className="absolute top-0 right-0 -mt-8 -mr-8 w-40 h-40 bg-sky-400/10 rounded-full blur-2xl" />
            <div className="flex items-start gap-6 relative z-10">
              <div className="size-16 bg-white rounded-xl shadow-sm border border-border-subtle flex items-center justify-center shrink-0 text-success">
                <span className="material-symbols-outlined text-4xl" aria-hidden="true">
                  task_alt
                </span>
              </div>
              <div className="flex-1 pt-1">
                <div className="flex items-center gap-3 mb-2">
                  <h2 className="text-xl font-bold text-text-main">
                    Translation Successful
                  </h2>
                  <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wide ${
                    isWritingToSheet
                      ? "bg-sky-50 text-sky-600 border border-sky-200"
                      : "bg-emerald-50 text-emerald-600 border border-emerald-200"
                  }`}>
                    {isWritingToSheet ? (
                      <span className="inline-flex items-center gap-1.5">
                        <span className="material-symbols-outlined text-xs animate-spin360">progress_activity</span>
                        Writing...
                      </span>
                    ) : translationsApplied ? "Pushed" : "Ready to Push"}
                  </span>
                </div>
                <p className="text-text-muted text-base leading-relaxed mb-6">
                  <strong className="text-text-main">
                    {totalRows || reviewResults.length} rows
                  </strong>{" "}
                  processed across{" "}
                  <strong className="text-text-main">
                    {langCount} languages
                  </strong>
                  . {failedRows.length > 0
                    ? `${failedRows.length} items failed validation (tag mismatch after 3 retries).`
                    : "All validations passed successfully."}
                </p>
                <div className="w-full bg-white/50 rounded-full h-3 mb-2 border border-primary/20">
                  <div className="bg-success h-full rounded-full w-full shadow-[0_0_10px_rgba(16,185,129,0.4)]" />
                </div>
                <div className="flex justify-between text-xs font-medium text-text-muted">
                  <span>Validation Progress</span>
                  <span>100%</span>
                </div>
              </div>
            </div>
          </div>

          {/* Metric cards */}
          <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 ${STAGGER}`} style={staggerDelay(2)}>
            <MetricCard
              icon="token"
              iconColor="bg-orange-50 text-orange-500"
              label="Tokens Used"
              value={totalTokens.toLocaleString()}
              sub={[
                cachedTokens > 0 ? `Cached: ${cachedTokens.toLocaleString()}` : "",
                reasoningTokens > 0 ? `Reasoning: ${reasoningTokens.toLocaleString()}` : "",
              ].filter(Boolean).join(" · ") || undefined}
              badge="Grok"
            />
            <MetricCard
              icon="table_rows"
              iconColor="bg-sky-50 text-sky-500"
              label="Rows Translated"
              value={String(totalRows || reviewResults.length)}
              badge={`${langCount} Langs`}
            />
            <MetricCard
              icon="edit_note"
              iconColor="bg-purple-50 text-purple-500"
              label="Cells Updated"
              value={isWritingToSheet ? "..." : String(cellsUpdated)}
              badge=""
            />
            <MetricCard
              icon="attach_money"
              iconColor="bg-green-50 text-green-600"
              label="Total Cost"
              value={`$${estimatedCost.toFixed(4)}`}
              badge="Est."
            />
          </div>
        </div>
      </main>

      <Footer
        showCancel={false}
        showExport
        onExport={() => {
          if (sessionId)
            window.open(getDownloadUrl(sessionId, "translation_report"));
        }}
        onAction={() => reset()}
        actionLabel={isWritingToSheet ? "Writing to Sheet..." : "New Session"}
        actionIcon={isWritingToSheet ? "progress_activity" : "arrow_forward"}
        actionDisabled={isWritingToSheet}
      />
    </>
  );
}

function MetricCard({
  icon,
  iconColor,
  label,
  value,
  badge,
  sub,
}: {
  icon: string;
  iconColor: string;
  label: string;
  value: string;
  badge: string;
  sub?: string;
}) {
  return (
    <div className="bg-bg-surface border border-border-subtle p-6 rounded-xl shadow-soft hover:shadow-md transition-shadow duration-200 flex flex-col items-center text-center">
      <div className={`p-3 rounded-full ${iconColor} mb-3`}>
        <span className="material-symbols-outlined text-2xl" aria-hidden="true">{icon}</span>
      </div>
      <p className="text-text-muted text-xs font-medium uppercase tracking-wider mb-1">
        {label}
      </p>
      <p className="text-3xl font-bold text-text-main mb-2">{value}</p>
      {sub && (
        <p className="text-xs text-text-muted mb-1">{sub}</p>
      )}
      {badge && (
        <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-surface-pale text-text-muted">
          {badge}
        </span>
      )}
    </div>
  );
}
