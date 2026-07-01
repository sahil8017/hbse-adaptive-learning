'use client';

import { useEffect, useRef, useState } from 'react';
import { Send, Bot, User, Trash2, PlayCircle } from 'lucide-react';
import { api, apiStream } from '@/lib/api';
import type { ChatMessage } from '@/lib/types';
import MathText from '@/components/MathText';
import { BasePageLoader } from '@/components/Loading';

interface YouTubeRec {
  title: string;
  search_query: string;
  video_url: string;
  reason: string;
  channel?: string;
  duration?: string;
  thumbnail_url?: string;
}

export default function TutorPage() {
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState('');
  const [youtubeRec, setYoutubeRec] = useState<YouTubeRec | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.get<ChatMessage[]>('/chat/history')
      .then((data) => {
        setHistory(data);
        setIsLoading(false);
      })
      .catch(() => {
        setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history, streamText, youtubeRec]);

  if (isLoading) {
    return <BasePageLoader pageType="tutor" />;
  }


  const sendMessage = async () => {
    const msg = input.trim();
    if (!msg || streaming) return;
    setInput('');

    const userMsg: ChatMessage = { sender: 'user', message: msg, is_blocked: false, timestamp: new Date().toISOString() };
    setHistory((prev) => [...prev, userMsg]);

    setStreaming(true);
    setStreamText('');
    setYoutubeRec(null);
    let fullText = '';

    try {
      const stream = apiStream('/chat/ask', 'POST', {
        message: msg,
        history: history.slice(-10).map((h) => ({ role: h.sender === 'user' ? 'user' : 'assistant', content: h.message })),
      });

      for await (const chunk of stream) {
        if (chunk.text) {
          fullText += chunk.text;
          // Strip any ---YOUTUBE_REC--- block that leaked through before backend stopped streaming
          setStreamText(fullText.replace(/\n*---(?:YOUTUBE_REC|YOUTUBE|YOUTUB|YOUT|YOU|YO|Y)?[\s\S]*/g, '').trimEnd());
        }
        if (chunk.type === 'youtube_rec' && chunk.video) {
          setYoutubeRec(chunk.video as YouTubeRec);
        }
        if (chunk.done) break;
      }
    } catch {
      fullText = 'Sorry, the tutor is temporarily unavailable. Please try again.';
      setStreamText(fullText);
    }

    const cleanText = fullText.replace(/\n*---(?:YOUTUBE_REC|YOUTUBE|YOUTUB|YOUT|YOU|YO|Y)?[\s\S]*/g, '').trimEnd();
    const aiMsg: ChatMessage = { sender: 'ai', message: cleanText, is_blocked: false, timestamp: new Date().toISOString() };
    setHistory((prev) => [...prev, aiMsg]);
    setStreamText('');
    setStreaming(false);
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const clearHistory = async () => {
    if (!confirm('Clear chat history? This cannot be undone.')) return;
    try {
      await api.del('/chat/history');
      setHistory([]);
    } catch {
      console.error('Failed to clear history');
    }
  };

  return (
    <div className="max-w-3xl mx-auto flex flex-col" style={{ height: 'calc(100dvh - 160px)' }}>
      <div className="mb-3 flex items-start justify-between">
        <div>
          <h1 className="font-heading text-lg sm:text-xl font-bold text-stone-900">AI Tutor</h1>
          <p className="text-stone-500 text-xs sm:text-sm">Ask anything about your Class 9 HBSE curriculum</p>
        </div>
        {history.length > 0 && (
          <button
            onClick={clearHistory}
            title="Clear chat history"
            className="p-2 hover:bg-stone-100 rounded-lg transition-colors text-stone-500 hover:text-red-600"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {history.length === 0 && !streaming && (
          <div className="flex flex-col items-center justify-center h-40 text-stone-400 text-sm gap-2">
            <Bot className="w-8 h-8" />
            <span>Ask me anything about your syllabus</span>
          </div>
        )}

        {history.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.sender === 'ai' && (
              <div className="w-8 h-8 rounded-full bg-teal-100 flex items-center justify-center shrink-0 mt-0.5">
                <Bot className="w-4 h-4 text-teal-700" />
              </div>
            )}
            <div className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
              msg.sender === 'user'
                ? 'bg-teal-600 text-white rounded-tr-sm'
                : msg.is_blocked
                ? 'bg-rose-50 text-rose-700 border border-rose-200 rounded-tl-sm'
                : 'bg-white border border-stone-200 text-stone-800 rounded-tl-sm'
            }`}>
              {msg.sender === 'ai' ? <MathText text={msg.message} /> : msg.message}
            </div>
            {msg.sender === 'user' && (
              <div className="w-8 h-8 rounded-full bg-stone-200 flex items-center justify-center shrink-0 mt-0.5">
                <User className="w-4 h-4 text-stone-600" />
              </div>
            )}
          </div>
        ))}

        {/* Streaming bubble */}
        {streaming && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-full bg-teal-100 flex items-center justify-center shrink-0 mt-0.5">
              <Bot className="w-4 h-4 text-teal-700" />
            </div>
            <div className="max-w-[80%] px-4 py-3 rounded-2xl rounded-tl-sm bg-white border border-stone-200 text-stone-800 text-sm leading-relaxed whitespace-pre-wrap">
              {streamText ? <MathText text={streamText} /> : <span className="text-stone-400 text-sm">Thinking…</span>}
              {streamText && <span className="streaming-cursor" />}
            </div>
          </div>
        )}

        {/* YouTube Recommendation Card */}
        {youtubeRec && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-full bg-teal-100 flex items-center justify-center shrink-0 mt-0.5">
              <PlayCircle className="w-4 h-4 text-red-600" />
            </div>
            <div className="max-w-[80%] bg-white border border-stone-200 rounded-2xl rounded-tl-sm overflow-hidden hover:shadow-md transition-shadow">
              <a href={youtubeRec.video_url} target="_blank" rel="noopener noreferrer" className="block">
                {/* Thumbnail — real image when available, branded placeholder otherwise */}
                <div className="relative w-full aspect-video bg-stone-100 overflow-hidden">
                  {youtubeRec.thumbnail_url ? (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={youtubeRec.thumbnail_url}
                      alt={youtubeRec.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center gap-2 bg-gradient-to-br from-red-50 to-stone-100">
                      <PlayCircle className="w-10 h-10 text-red-400" />
                      <span className="text-xs text-stone-400">Watch on YouTube</span>
                    </div>
                  )}
                  {/* Play overlay */}
                  <div className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity bg-black/20">
                    <div className="w-12 h-12 rounded-full bg-red-600 flex items-center justify-center shadow-lg">
                      <PlayCircle className="w-6 h-6 text-white" />
                    </div>
                  </div>
                </div>

                <div className="p-4 space-y-1.5">
                  <h3 className="font-semibold text-stone-900 text-sm line-clamp-2 leading-snug">
                    {youtubeRec.title}
                  </h3>
                  {(youtubeRec.channel || youtubeRec.duration) && (
                    <p className="text-xs text-stone-500">
                      {youtubeRec.channel && <span>{youtubeRec.channel}</span>}
                      {youtubeRec.channel && youtubeRec.duration && <span> • </span>}
                      {youtubeRec.duration && <span>{youtubeRec.duration}</span>}
                    </p>
                  )}
                  <p className="text-xs text-stone-600 leading-relaxed">
                    {youtubeRec.reason}
                  </p>
                  <span className="inline-flex items-center gap-1 text-red-600 text-xs font-medium pt-1">
                    <PlayCircle className="w-3.5 h-3.5" />
                    Watch on YouTube
                  </span>
                </div>
              </a>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="pt-3 border-t border-stone-200 mt-3">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask a question…"
            rows={2}
            disabled={streaming}
            className="flex-1 px-3 sm:px-4 py-2.5 bg-white border border-stone-300 rounded-xl text-sm text-stone-800 placeholder-stone-400 resize-none focus:outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-100 disabled:opacity-60"
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || streaming}
            className="px-4 py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="hidden sm:block text-xs text-stone-400 mt-1.5 pl-1">Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  );
}
