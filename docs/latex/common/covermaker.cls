% covermaker.cls -- shared document class for Cover_Maker documentation.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{covermaker}[2026/11/03 Cover_Maker documentation class]

\LoadClass[11pt,a4paper,oneside,parskip=half,headings=big]{scrreprt}

% ---------------------------------------------------------------- Fonts ----
\RequirePackage{fontspec}
\RequirePackage{libertinus}
\RequirePackage[english]{babel}
\RequirePackage{microtype}
% Long monospaced names (paths, identifiers) cannot be hyphenated; let TeX
% stretch the spaces of such lines instead of pushing text into the margin.
\setlength{\emergencystretch}{3em}
\tolerance=2000

% --------------------------------------------------------------- Layout ----
\RequirePackage[margin=2.5cm,headheight=15pt]{geometry}
\RequirePackage{xcolor}
\definecolor{cmaccent}{HTML}{6B4EFF}
\definecolor{cmmuted}{HTML}{5D5D6B}
\definecolor{cmsoft}{HTML}{EBE8FF}
\addtokomafont{disposition}{\color{cmaccent}}

\RequirePackage[automark]{scrlayer-scrpage}
\clearpairofpagestyles
\ihead{\textcolor{cmmuted}{\cmdoctitle}}
\ohead{\textcolor{cmmuted}{\cmdocid}}
\ifoot{\textcolor{cmmuted}{Cover\_Maker \textbullet{} \cmgitversion}}
\ofoot{\pagemark}

% --------------------------------------------------------------- Tables ----
\RequirePackage{booktabs}
\RequirePackage{tabularx}
\RequirePackage{longtable}
\RequirePackage{array}
\newcolumntype{Y}{>{\raggedright\arraybackslash}X}
\newcolumntype{P}[1]{>{\raggedright\arraybackslash}p{#1}}

% ----------------------------------------------------------- Misc tools ----
\RequirePackage{enumitem}
\setlist{nosep,leftmargin=*}
\RequirePackage{graphicx}
\RequirePackage{tikz}
\usetikzlibrary{arrows.meta,positioning,shapes.geometric,fit,backgrounds}
\RequirePackage{listings}
\lstset{
  basicstyle=\ttfamily\small,
  columns=fullflexible,
  frame=single,
  rulecolor=\color{cmmuted},
  backgroundcolor=\color{cmsoft!40},
  breaklines=true,
  showstringspaces=false,
}
\RequirePackage[hidelinks]{hyperref}
\RequirePackage[noredefwarn]{glossaries}
\makenoidxglossaries

% ------------------------------------------------------------ Metadata ----
\InputIfFileExists{version.tex}{}{\def\cmgitversion{dev}}
\newcommand\cmdoctitle{Untitled}
\newcommand\cmdocsubtitle{}
\newcommand\cmdocid{CM-XXX}
\newcommand\cmdocstatus{Draft}
\newcommand\cmdocdate{\today}
\newcommand\doctitle[1]{\renewcommand\cmdoctitle{#1}}
\newcommand\docsubtitle[1]{\renewcommand\cmdocsubtitle{#1}}
\newcommand\docid[1]{\renewcommand\cmdocid{#1}}
\newcommand\docstatus[1]{\renewcommand\cmdocstatus{#1}}
\newcommand\docdate[1]{\renewcommand\cmdocdate{#1}}

\AtBeginDocument{\hypersetup{pdftitle={Cover\_Maker -- \cmdoctitle},pdfauthor={Cover\_Maker contributors}}}

% ----------------------------------------------------------- Title page ----
\newcommand\cmtitlepage{%
  \begin{titlepage}
    \thispagestyle{empty}
    {\color{cmaccent}\rule{\linewidth}{2pt}}\par\vspace{2cm}
    {\Huge\bfseries\color{cmaccent} Cover\_Maker\par}
    \vspace{0.5cm}
    {\LARGE\bfseries \cmdoctitle\par}
    \vspace{0.3cm}
    {\large\color{cmmuted} \cmdocsubtitle\par}
    \vfill
    \begin{tabular}{@{}ll@{}}
      \textbf{Document ID} & \cmdocid \\
      \textbf{Version} & \cmgitversion \\
      \textbf{Status} & \cmdocstatus \\
      \textbf{Date} & \cmdocdate \\
      \textbf{Licence} & MIT (code) / CC BY 4.0 (documentation) \\
    \end{tabular}
    \par\vspace{1cm}
    {\color{cmaccent}\rule{\linewidth}{2pt}}
  \end{titlepage}
}

% ------------------------------------------------------ Revision history ----
% Usage: \begin{revisionhistory} 0.1 & 2026-11-03 & Initial draft \\ \end{revisionhistory}
\newenvironment{revisionhistory}{%
  \section*{Revision history}
  \tabularx{\linewidth}{@{}llY@{}}
    \toprule
    \textbf{Version} & \textbf{Date} & \textbf{Changes} \\
    \midrule
}{%
    \bottomrule
  \endtabularx
}

% ------------------------------------------------------------ Shortcuts ----
\newcommand\CM{Cover\_Maker}
\newcommand\todoin[1]{\cmnote{\textbf{To be completed in #1.}}}

% ------------------------------------------------------------ Callouts ----
\newcommand\cmnote[1]{%
  \par\noindent\fcolorbox{cmaccent}{cmsoft}{\parbox{\dimexpr\linewidth-2\fboxsep-2\fboxrule}{#1}}\par}

\endinput
