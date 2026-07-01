'use client';

import { useMemo, ReactNode } from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';

interface Segment {
  type: 'text' | 'math';
  value: string;
}

function parseSegments(raw: string | undefined | null): Segment[] {
  if (!raw) return [];
  const segments: Segment[] = [];
  // Match $$...$$ (display) or $...$ (inline), non-greedy
  const re = /\$\$([^$]+?)\$\$|\$([^$\n]+?)\$/g;
  let last = 0;
  let m: RegExpExecArray | null;

  while ((m = re.exec(raw)) !== null) {
    if (m.index > last) {
      segments.push({ type: 'text', value: raw.slice(last, m.index) });
    }
    segments.push({ type: 'math', value: m[1] ?? m[2] });
    last = m.index + m[0].length;
  }
  if (last < raw.length) {
    segments.push({ type: 'text', value: raw.slice(last) });
  }
  return segments;
}

function KatexSpan({ tex }: { tex: string }) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(tex, { throwOnError: false, output: 'html' });
    } catch {
      return tex;
    }
  }, [tex]);

  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}

function formatItalics(text: string): (string | ReactNode)[] {
  const italicRe = /\*([^*]+?)\*/g;
  const parts: (string | ReactNode)[] = [];
  let last = 0;
  let m: RegExpExecArray | null;

  while ((m = italicRe.exec(text)) !== null) {
    if (m.index > last) {
      parts.push(text.slice(last, m.index));
    }
    parts.push(<em key={`i-${m.index}`} className="italic">{m[1]}</em>);
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    parts.push(text.slice(last));
  }
  return parts;
}

function formatMarkdownInline(text: string): (string | ReactNode)[] {
  const boldRe = /\*\*([^*]+?)\*\*/g;
  const parts: (string | ReactNode)[] = [];
  let last = 0;
  let m: RegExpExecArray | null;

  while ((m = boldRe.exec(text)) !== null) {
    if (m.index > last) {
      parts.push(...formatItalics(text.slice(last, m.index)));
    }
    parts.push(<strong key={`b-${m.index}`} className="font-semibold text-stone-900">{m[1]}</strong>);
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    parts.push(...formatItalics(text.slice(last)));
  }
  return parts;
}

function RenderText({ value }: { value: string }) {
  const re = /\[img:\s*([^\]]+)\]/g;
  const parts: (string | ReactNode)[] = [];
  let last = 0;
  let m: RegExpExecArray | null;

  while ((m = re.exec(value)) !== null) {
    if (m.index > last) {
      parts.push(value.slice(last, m.index));
    }
    const src = m[1].trim();
    // Block non-http(s) schemes (javascript:, data:, vbscript:, etc.)
    if (/^(https?:\/\/|\/)/i.test(src)) {
      parts.push(
        /* eslint-disable-next-line @next/next/no-img-element */
        <img
          key={m.index}
          src={src}
          alt="Question Diagram"
          className="my-4 mx-auto max-w-full sm:max-w-md h-auto block rounded-xl border border-stone-200 shadow-sm bg-white p-2"
        />
      );
    }
    last = m.index + m[0].length;
  }
  if (last < value.length) {
    parts.push(value.slice(last));
  }

  return (
    <>
      {parts.map((p, i) => (
        typeof p === 'string' ? <span key={i}>{formatMarkdownInline(p)}</span> : p
      ))}
    </>
  );
}

export default function MathText({
  text,
  className,
}: {
  text: string | undefined | null;
  className?: string;
}) {
  const segments = useMemo(() => parseSegments(text), [text]);

  return (
    <span className={className}>
      {segments.map((seg, i) =>
        seg.type === 'math' ? (
          <KatexSpan key={i} tex={seg.value} />
        ) : (
          <RenderText key={i} value={seg.value} />
        ),
      )}
    </span>
  );
}
