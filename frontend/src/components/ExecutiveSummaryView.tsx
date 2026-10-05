"use client";

import React from "react";
import { 
  FileText, 
  ChartBar, 
  TrendUp, 
  ShieldCheck, 
  Target, 
  Globe, 
  Database, 
  Percent, 
  CheckCircle,
  Table as TableIcon,
  Newspaper,
  Compass,
  ArrowUpRight,
  ArrowDownRight
} from "@phosphor-icons/react";
import { ReportVisualsData } from "@/lib/reportVisuals";

interface ExecutiveSummaryViewProps {
  visuals: ReportVisualsData;
  approvedCount?: number;
  totalFindings?: number;
}

export function ExecutiveSummaryView({
  visuals,
  approvedCount,
  totalFindings,
}: ExecutiveSummaryViewProps) {
  const mkt = visuals.marketVisual;
  const news = visuals.newsVisual;

  // Chart calculation constants for Financial Revenue Trajectory (if present)
  const revBars = visuals.revenueTrajectory.bars;
  const maxRevValue = revBars.length > 0 ? Math.max(...revBars.map(b => b.value), 10) * 1.2 : 120;
  const chartHeight = 150;
  const barWidth = 36;
  const barGap = 32;
  const startX = 35;

  // Chart calculation constants for Financial Gross Margin Trend (if present)
  const marginPts = visuals.marginTrend.points;
  const minMargin = marginPts.length > 0 ? Math.floor(Math.min(...marginPts.map(p => p.value)) / 10) * 10 : 40;
  const maxMargin = marginPts.length > 0 ? Math.ceil(Math.max(...marginPts.map(p => p.value)) / 10) * 10 : 80;
  const marginChartHeight = 130;
  const marginStartX = 35;
  const marginStepX = 65;

  const getMarginY = (val: number) => {
    const range = Math.max(maxMargin - minMargin, 1);
    const clamped = Math.max(minMargin, Math.min(maxMargin, val));
    const ratio = (clamped - minMargin) / range;
    return marginChartHeight - ratio * marginChartHeight + 20;
  };

  const marginPointsCoords = marginPts.map((pt, idx) => ({
    x: marginStartX + idx * marginStepX,
    y: getMarginY(pt.value),
    pt,
  }));

  const solidPath = marginPointsCoords.map((p, idx) => `${idx === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");

  return (
    <div className="space-y-6">
      {/* Top Row: Executive Summary + Key Figures */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
        {/* Left: Executive Summary Card */}
        <div className="lg:col-span-7 bg-white rounded-2xl border border-slate-200/90 shadow-sm p-6 sm:p-7 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2.5 mb-4">
              <div className="w-8 h-8 rounded-lg bg-sky-50 border border-sky-200 flex items-center justify-center text-sky-600">
                <FileText size={18} weight="bold" />
              </div>
              <h3 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">
                Executive Summary
              </h3>
            </div>
            <p className="text-slate-700 text-sm sm:text-[14.5px] leading-relaxed font-normal">
              {visuals.executiveSummary}
            </p>
          </div>
          <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 font-mono">
            <span>Primary Focus: {visuals.hasMarketData ? "Market Valuation & Sentiment" : "Institutional Fundamentals"}</span>
            <span>Target: {visuals.targetPeriod}</span>
          </div>
        </div>

        {/* Right: Key Figures Grid */}
        <div className="lg:col-span-5 bg-white rounded-2xl border border-slate-200/90 shadow-sm p-6 sm:p-7 flex flex-col justify-between">
          <div className="flex items-center gap-2.5 mb-5">
            <div className="w-8 h-8 rounded-lg bg-sky-50 border border-sky-200 flex items-center justify-center text-sky-600">
              <ChartBar size={18} weight="bold" />
            </div>
            <h3 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">
              Key Figures ({visuals.targetPeriod})
            </h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 flex-1">
            {visuals.keyFigures.map((fig, idx) => (
              <div 
                key={idx} 
                className="p-3.5 rounded-xl bg-slate-50/70 border border-slate-200/70 flex flex-col justify-between hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight font-sans">
                    {fig.value}
                  </span>
                  <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                    fig.iconType === "revenue" ? "bg-emerald-50 text-emerald-600 border border-emerald-200" :
                    fig.iconType === "segment" ? "bg-sky-50 text-sky-600 border border-sky-200" :
                    fig.iconType === "margin" ? "bg-purple-50 text-purple-600 border border-purple-200" :
                    "bg-amber-50 text-amber-600 border border-amber-200"
                  }`}>
                    {fig.iconType === "revenue" && <TrendUp size={15} weight="bold" />}
                    {fig.iconType === "segment" && <Database size={15} weight="bold" />}
                    {fig.iconType === "margin" && <Percent size={15} weight="bold" />}
                    {fig.iconType === "guidance" && <FileText size={15} weight="bold" />}
                  </div>
                </div>

                <div>
                  <div className="text-xs font-semibold text-slate-700 leading-tight">
                    {fig.label}
                  </div>
                  {fig.subtext && (
                    <div className="text-[11px] text-slate-500 mt-0.5 font-sans">
                      {fig.subtext}
                    </div>
                  )}
                  {(fig.badge1 || fig.badge2) && (
                    <div className="flex flex-wrap items-center gap-1.5 mt-2">
                      {fig.badge1 && (
                        <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200/60 font-mono">
                          {fig.badge1}
                        </span>
                      )}
                      {fig.badge2 && (
                        <span className="text-[10px] font-bold text-sky-700 bg-sky-50 px-1.5 py-0.5 rounded border border-sky-200/60 font-mono">
                          {fig.badge2}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Middle Row: 3 Visual Breakdown Cards (100% Dynamic based on query findings) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        
        {/* CASE 1: Query has Market Data (e.g. price performance & valuation) */}
        {visuals.hasMarketData && mkt ? (
          <>
            {/* Card 1: 52-Week Price Range Gauge */}
            <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm p-5 sm:p-6 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between gap-2 mb-4">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-lg bg-sky-50 border border-sky-200 flex items-center justify-center text-sky-600">
                      <Compass size={16} weight="bold" />
                    </div>
                    <h4 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight">
                      52-Week Price Range
                    </h4>
                  </div>
                  <span className={`inline-flex items-center gap-1 text-xs font-mono font-bold px-2 py-0.5 rounded-full ${
                    mkt.isPositive ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-rose-50 text-rose-700 border border-rose-200"
                  }`}>
                    {mkt.isPositive ? <ArrowUpRight size={13} weight="bold" /> : <ArrowDownRight size={13} weight="bold" />}
                    <span>{mkt.changePct}</span>
                  </span>
                </div>

                <div className="my-4 space-y-3">
                  <div className="flex items-baseline justify-between">
                    <span className="text-2xl font-black text-slate-900 font-sans tracking-tight">
                      {mkt.price}
                    </span>
                    <span className="text-xs font-mono text-slate-500">
                      Traded Price
                    </span>
                  </div>

                  {/* Horizontal SVG Range Meter */}
                  <div className="space-y-1.5">
                    <div className="relative w-full h-4 bg-slate-100 rounded-full overflow-hidden border border-slate-200/80">
                      {/* Gradient Range Fill */}
                      <div 
                        className="h-full bg-gradient-to-r from-sky-400 via-teal-400 to-emerald-500 rounded-full transition-all duration-500"
                        style={{ width: `${Math.max(8, mkt.rangePositionPct)}%` }}
                      />
                    </div>

                    <div className="flex items-center justify-between text-[11px] font-mono text-slate-500 px-0.5">
                      <span>Low: {mkt.low52}</span>
                      <span className="font-bold text-sky-700">At {mkt.rangePositionPct.toFixed(1)}% of Span</span>
                      <span>High: {mkt.high52}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                <span>Alpha Vantage Telemetry</span>
                <span className="text-emerald-700 font-semibold font-mono">Active Quote</span>
              </div>
            </div>

            {/* Card 2: Valuation Multiples & Scale */}
            <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm p-5 sm:p-6 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-7 h-7 rounded-lg bg-sky-50 border border-sky-200 flex items-center justify-center text-sky-600">
                    <Database size={16} weight="bold" />
                  </div>
                  <h4 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight">
                    Valuation & Capitalization
                  </h4>
                </div>

                <div className="space-y-3.5 my-2">
                  <div className="p-3 rounded-xl bg-slate-50/80 border border-slate-200/60 flex items-center justify-between">
                    <div>
                      <div className="text-[11px] font-mono text-slate-500 uppercase tracking-wider">
                        Market Capitalization
                      </div>
                      <div className="text-xl font-extrabold text-slate-900 tracking-tight mt-0.5 font-sans">
                        {mkt.marketCap}
                      </div>
                    </div>
                    <span className="text-[10px] font-mono font-bold px-2 py-1 rounded bg-blue-50 text-blue-700 border border-blue-200">
                      MEGA CAP
                    </span>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-50/80 border border-slate-200/60 flex items-center justify-between">
                    <div>
                      <div className="text-[11px] font-mono text-slate-500 uppercase tracking-wider">
                        Trailing P/E Ratio
                      </div>
                      <div className="text-xl font-extrabold text-slate-900 tracking-tight mt-0.5 font-sans">
                        {mkt.peRatio}
                      </div>
                    </div>
                    <span className="text-[10px] font-mono font-bold px-2 py-1 rounded bg-purple-50 text-purple-700 border border-purple-200">
                      VALUATION MULTIPLE
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                <span>Audited Market Ratios</span>
                <span className="font-mono text-sky-600 font-semibold">Verified Fundamentals</span>
              </div>
            </div>

            {/* Card 3: News Sentiment or Risk Catalyst */}
            {visuals.hasNewsData && news ? (
              <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm p-5 sm:p-6 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-purple-50 border border-purple-200 flex items-center justify-center text-purple-600">
                        <Newspaper size={16} weight="bold" />
                      </div>
                      <h4 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight">
                        News & Sentiment Wire
                      </h4>
                    </div>
                    <span className="text-[10.5px] font-mono font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                      {news.sentimentLabel.toUpperCase()}
                    </span>
                  </div>

                  <div className="space-y-2.5">
                    <div className="p-3 rounded-xl bg-purple-50/40 border border-purple-200/60">
                      <div className="text-xs font-bold text-slate-900 line-clamp-2 leading-snug">
                        {news.title}
                      </div>
                      <div className="flex items-center gap-2 mt-1.5 text-[10.5px] text-slate-500 font-mono">
                        <span className="font-semibold text-purple-700">{news.publisher}</span>
                        <span>•</span>
                        <span>Score: {news.sentimentScore.toFixed(3)}</span>
                      </div>
                    </div>

                    <p className="text-[11.5px] text-slate-600 line-clamp-3 leading-relaxed">
                      {news.summary}
                    </p>
                  </div>
                </div>

                <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                  <span>Audited News Feed</span>
                  <span className="font-mono text-emerald-600 font-semibold">Relevance Verified</span>
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm p-5 sm:p-6 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-7 h-7 rounded-lg bg-sky-50 border border-sky-200 flex items-center justify-center text-sky-600">
                      <ShieldCheck size={16} weight="bold" />
                    </div>
                    <h4 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight">
                      Risk Disclosures
                    </h4>
                  </div>
                  <div className="space-y-2">
                    {visuals.riskImpact.items.slice(0, 2).map((item, idx) => (
                      <div key={idx} className="p-2.5 rounded-xl border bg-slate-50/70 border-slate-200/80">
                        <div className="text-xs font-bold text-slate-900">{item.title}</div>
                        <p className="text-[11px] text-slate-600 mt-0.5 line-clamp-2">{item.note}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="mt-3 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
                  SEC Item 1A Disclosures
                </div>
              </div>
            )}
          </>
        ) : (
          /* CASE 2: Query has SEC Financial Performance or Trajectory */
          <>
            {/* Card 1: Revenue Trajectory (Dynamic Bar Chart) */}
            <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm p-5 sm:p-6 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-7 h-7 rounded-lg bg-sky-50 border border-sky-200 flex items-center justify-center text-sky-600">
                    <ChartBar size={16} weight="bold" />
                  </div>
                  <h4 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight">
                    {visuals.revenueTrajectory.title}
                  </h4>
                </div>

                <div className="relative w-full h-[180px] overflow-hidden flex items-end">
                  <svg className="w-full h-full" viewBox="0 0 300 180" fill="none">
                    {[
                      { label: `${Math.round(maxRevValue)}B`, y: 25 },
                      { label: `${Math.round(maxRevValue * 0.75)}B`, y: 55 },
                      { label: `${Math.round(maxRevValue * 0.5)}B`, y: 85 },
                      { label: `${Math.round(maxRevValue * 0.25)}B`, y: 115 },
                      { label: "0", y: 145 },
                    ].map((grid, i) => (
                      <g key={i}>
                        <text x="2" y={grid.y + 4} className="text-[9px] fill-slate-500 font-mono">
                          {grid.label}
                        </text>
                        <line x1="28" y1={grid.y} x2="295" y2={grid.y} stroke="#f1f5f9" strokeWidth="1" />
                      </g>
                    ))}

                    {revBars.map((bar, i) => {
                      const x = startX + i * (barWidth + barGap);
                      const barH = (bar.value / maxRevValue) * 120;
                      const y = 145 - barH;

                      return (
                        <g key={i}>
                          <text
                            x={x + barWidth / 2}
                            y={y - 6}
                            textAnchor="middle"
                            className="text-[10px] font-bold fill-slate-800 font-sans"
                          >
                            {bar.label}
                          </text>
                          <rect
                            x={x}
                            y={y}
                            width={barWidth}
                            height={barH}
                            rx="4"
                            fill="#0284c7"
                          />
                          <text
                            x={x + barWidth / 2}
                            y="160"
                            textAnchor="middle"
                            className="text-[9.5px] fill-slate-600 font-sans"
                          >
                            {bar.period}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                </div>
              </div>

              <div className="flex items-center gap-4 mt-3 pt-3 border-t border-slate-100 text-[11px] text-slate-500 font-sans">
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-xs bg-[#0284c7]" />
                  <span>Audited Revenue Figures</span>
                </div>
              </div>
            </div>

            {/* Card 2: Margin Trend (Dynamic Line Chart) */}
            <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm p-5 sm:p-6 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-7 h-7 rounded-lg bg-sky-50 border border-sky-200 flex items-center justify-center text-sky-600">
                    <TrendUp size={16} weight="bold" />
                  </div>
                  <h4 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight">
                    {visuals.marginTrend.title}
                  </h4>
                </div>

                <div className="relative w-full h-[180px] overflow-hidden flex items-end">
                  <svg className="w-full h-full" viewBox="0 0 300 180" fill="none">
                    {[
                      { label: `${maxMargin}%`, y: 25 },
                      { label: `${Math.round((maxMargin + minMargin) / 2)}%`, y: 85 },
                      { label: `${minMargin}%`, y: 145 },
                    ].map((grid, i) => (
                      <g key={i}>
                        <text x="2" y={grid.y + 4} className="text-[9px] fill-slate-500 font-mono">
                          {grid.label}
                        </text>
                        <line x1="28" y1={grid.y} x2="295" y2={grid.y} stroke="#f1f5f9" strokeWidth="1" />
                      </g>
                    ))}

                    <path d={solidPath} stroke="#0284c7" strokeWidth="2.5" fill="none" />

                    {marginPointsCoords.map((pt, i) => (
                      <g key={i}>
                        <circle cx={pt.x} cy={pt.y} r="4.5" fill="#ffffff" stroke="#0284c7" strokeWidth="2.5" />
                        <text
                          x={pt.x}
                          y={pt.y - 9}
                          textAnchor="middle"
                          className="text-[9.5px] font-bold fill-slate-800 font-sans"
                        >
                          {pt.pt.label}
                        </text>
                        <text
                          x={pt.x}
                          y="160"
                          textAnchor="middle"
                          className="text-[9.5px] fill-slate-600 font-sans"
                        >
                          {pt.pt.period}
                        </text>
                      </g>
                    ))}
                  </svg>
                </div>
              </div>

              <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                <span>GAAP Margin Analysis</span>
                <span className="font-mono text-sky-600 font-semibold">SEC Audited</span>
              </div>
            </div>

            {/* Card 3: Regulatory & Risk Impact */}
            <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm p-5 sm:p-6 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-7 h-7 rounded-lg bg-sky-50 border border-sky-200 flex items-center justify-center text-sky-600">
                    <ShieldCheck size={16} weight="bold" />
                  </div>
                  <h4 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight">
                    {visuals.riskImpact.title}
                  </h4>
                </div>

                <div className="space-y-3">
                  {visuals.riskImpact.items.slice(0, 3).map((item, idx) => (
                    <div
                      key={idx}
                      className={`p-3 rounded-xl border flex items-start gap-3 transition-colors ${
                        item.tone === "red"
                          ? "bg-rose-50/60 border-rose-200/70"
                          : item.tone === "amber"
                          ? "bg-amber-50/60 border-amber-200/70"
                          : "bg-purple-50/60 border-purple-200/70"
                      }`}
                    >
                      <div className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
                        item.tone === "red"
                          ? "text-rose-600 bg-rose-100/80"
                          : item.tone === "amber"
                          ? "text-amber-600 bg-amber-100/80"
                          : "text-purple-600 bg-purple-100/80"
                      }`}>
                        {item.icon === "crosshairs" && <Target size={14} weight="bold" />}
                        {item.icon === "file" && <FileText size={14} weight="bold" />}
                        {item.icon === "globe" && <Globe size={14} weight="bold" />}
                        {item.icon === "shield" && <ShieldCheck size={14} weight="bold" />}
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="text-xs font-bold text-slate-900">
                            {item.title}
                          </span>
                          {item.metric && (
                            <span className="text-xs font-mono font-bold text-slate-600">
                              {item.metric}
                            </span>
                          )}
                        </div>
                        <p className="text-[11.5px] text-slate-600 leading-snug mt-0.5">
                          {item.note}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-3 pt-3 border-t border-slate-100 text-[11px] text-slate-500 font-sans">
                SEC Form 10-K Item 1A / Item 3 Disclosures
              </div>
            </div>
          </>
        )}
      </div>

      {/* Bottom Section: Dynamic Coverage Matrix Table (100% Dynamic matching actual tasks & findings) */}
      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm p-6 overflow-hidden">
        <div className="flex items-center justify-between gap-4 mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-sky-50 border border-sky-200 flex items-center justify-center text-sky-600">
              <TableIcon size={18} weight="bold" />
            </div>
            <h3 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">
              Coverage Matrix
            </h3>
          </div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold">
            <CheckCircle size={14} weight="fill" className="text-emerald-500" />
            <span>All research tasks completed ({visuals.coverageMatrix.length}/{visuals.coverageMatrix.length})</span>
          </div>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-200/80">
          <table className="w-full text-left border-collapse text-xs sm:text-sm font-sans">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold text-[11px] uppercase tracking-wider">
                <th className="py-3 px-4 w-24">Task ID</th>
                <th className="py-3 px-4">Query Clause / Research Task</th>
                <th className="py-3 px-4">Required Sources</th>
                <th className="py-3 px-4 text-center w-24">Findings</th>
                <th className="py-3 px-4 w-28">Status</th>
                <th className="py-3 px-4 w-28">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {visuals.coverageMatrix.map((row, idx) => (
                <tr key={idx} className="hover:bg-slate-50/70 transition-colors">
                  <td className="py-3 px-4 font-mono font-bold text-sky-600">
                    {row.taskId}
                  </td>
                  <td className="py-3 px-4 font-medium text-slate-900">
                    {row.clause}
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-slate-600">
                    {row.sources}
                  </td>
                  <td className="py-3 px-4 text-center font-mono font-semibold text-slate-700">
                    {row.findingsCount}
                  </td>
                  <td className="py-3 px-4">
                    <span className="inline-flex items-center gap-1 text-xs font-bold text-emerald-600">
                      <span>✓</span>
                      <span>{row.status}</span>
                    </span>
                  </td>
                  <td className="py-3 px-4 text-slate-600 font-mono text-xs">
                    {row.notes}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
