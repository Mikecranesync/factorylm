/**
 * PTTButton - Push-to-Talk voice interface
 *
 * Hold to record voice, release to send to AI.
 * Uses Web Speech API for transcription.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { Mic, Loader2 } from 'lucide-react';
import { hapticFeedback } from '../utils/telegram';

interface PTTButtonProps {
  onTranscript: (text: string) => Promise<string>;
  disabled?: boolean;
  className?: string;
}

type PTTState = 'idle' | 'recording' | 'processing';

export function PTTButton({ onTranscript, disabled = false, className = '' }: PTTButtonProps) {
  const [state, setState] = useState<PTTState>('idle');
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const responseTimeoutRef = useRef<number | null>(null);

  // Check for browser support
  const isSupported = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);

  // Initialize speech recognition
  useEffect(() => {
    if (!isSupported) return;

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();

    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcriptPart = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcriptPart;
        } else {
          interimTranscript += transcriptPart;
        }
      }

      setTranscript(finalTranscript || interimTranscript);
    };

    recognition.onerror = (event) => {
      console.error('[PTT] Speech recognition error:', event.error);
      setState('idle');
      setTranscript('');
    };

    recognition.onend = () => {
      // Only process if we were recording (not cancelled)
      if (state === 'recording') {
        // This will be handled by stopRecording
      }
    };

    recognitionRef.current = recognition;

    return () => {
      recognition.stop();
    };
  }, [isSupported]);

  const startRecording = useCallback(() => {
    if (!isSupported || disabled || !recognitionRef.current) return;

    try {
      recognitionRef.current.start();
      setState('recording');
      setTranscript('');
      setResponse(null);
      hapticFeedback('medium');

      // Clear any existing response timeout
      if (responseTimeoutRef.current) {
        clearTimeout(responseTimeoutRef.current);
      }
    } catch (error) {
      console.error('[PTT] Failed to start recording:', error);
    }
  }, [isSupported, disabled]);

  const stopRecording = useCallback(async () => {
    if (!recognitionRef.current || state !== 'recording') return;

    recognitionRef.current.stop();
    hapticFeedback('light');

    // Get final transcript
    const finalText = transcript.trim();

    if (finalText) {
      setState('processing');

      try {
        const aiResponse = await onTranscript(finalText);
        setResponse(aiResponse);
        hapticFeedback('success');

        // Clear response after 5 seconds
        responseTimeoutRef.current = window.setTimeout(() => {
          setResponse(null);
        }, 5000);
      } catch (error) {
        console.error('[PTT] Failed to process transcript:', error);
        setResponse('Error processing voice command');
        hapticFeedback('error');
      }
    }

    setState('idle');
    setTranscript('');
  }, [state, transcript, onTranscript]);

  // Handle touch/mouse events for PTT
  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    startRecording();
  }, [startRecording]);

  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    stopRecording();
  }, [stopRecording]);

  // Handle keyboard spacebar for PTT
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !e.repeat && state === 'idle' && !disabled) {
        e.preventDefault();
        startRecording();
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space' && state === 'recording') {
        e.preventDefault();
        stopRecording();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [state, disabled, startRecording, stopRecording]);

  if (!isSupported) {
    return (
      <div className={`text-center text-hmi-text-muted text-sm ${className}`}>
        Voice commands not supported in this browser
      </div>
    );
  }

  return (
    <div className={`flex flex-col items-center gap-3 ${className}`}>
      {/* Response bubble */}
      {response && (
        <div className="bg-hmi-panel border border-hmi-border rounded-lg p-3 max-w-full animate-in fade-in slide-in-from-bottom-2">
          <p className="text-sm text-hmi-text-normal">{response}</p>
        </div>
      )}

      {/* Transcript display */}
      {(state === 'recording' || state === 'processing') && transcript && (
        <div className="bg-hmi-inset border border-hmi-border rounded px-3 py-2 max-w-full">
          <p className="text-sm text-hmi-text-active font-mono italic">
            "{transcript}"
          </p>
        </div>
      )}

      {/* PTT Button */}
      <button
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onPointerLeave={stopRecording}
        disabled={disabled || state === 'processing'}
        className={`
          relative w-20 h-20
          rounded-full border-3
          flex items-center justify-center
          cursor-pointer select-none
          transition-all duration-150
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
          ${state === 'recording'
            ? `
                bg-gradient-to-b from-[#cc3333] via-[#aa2222] to-[#882222]
                border-[#ff4444]
                translate-y-1
                shadow-[inset_2px_2px_0_rgba(0,0,0,0.2),0_2px_0_#111,0_0_30px_rgba(255,0,0,0.5)]
                animate-ptt-glow
              `
            : state === 'processing'
            ? `
                bg-gradient-to-b from-[#4a4a4a] via-[#3a3a3a] to-[#2a2a2a]
                border-hmi-accent
                shadow-[0_4px_0_#1a1a1a,0_6px_8px_rgba(0,0,0,0.4)]
              `
            : `
                bg-gradient-to-b from-[#3a3a3a] via-[#2a2a2a] to-[#1a1a1a]
                border-[#555]
                shadow-[inset_2px_2px_0_rgba(255,255,255,0.1),0_6px_0_#111,0_8px_15px_rgba(0,0,0,0.5)]
                hover:bg-gradient-to-b hover:from-[#454545] hover:via-[#353535] hover:to-[#252525]
                active:translate-y-1 active:shadow-[0_2px_0_#111,0_3px_8px_rgba(0,0,0,0.4)]
              `
          }
        `}
      >
        {state === 'processing' ? (
          <Loader2 className="w-8 h-8 text-hmi-accent animate-spin" />
        ) : (
          <Mic
            className={`w-8 h-8 ${
              state === 'recording' ? 'text-white' : 'text-hmi-text-muted'
            }`}
          />
        )}

        {/* Recording indicator ring */}
        {state === 'recording' && (
          <div className="absolute inset-0 rounded-full border-4 border-red-500 animate-ping opacity-50" />
        )}
      </button>

      {/* Label */}
      <div className="text-center">
        <div className="text-hmi-text-label text-xs uppercase tracking-wider">
          {state === 'recording'
            ? 'Listening...'
            : state === 'processing'
            ? 'Processing...'
            : 'Hold to Speak'}
        </div>
        <div className="text-hmi-text-muted text-[10px] mt-0.5">
          Or hold SPACEBAR
        </div>
      </div>
    </div>
  );
}

// TypeScript declarations for Web Speech API
interface SpeechRecognitionEvent extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}

interface SpeechRecognitionResultList {
  length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  isFinal: boolean;
  length: number;
  item(index: number): SpeechRecognitionAlternative;
  [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message: string;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
}

interface SpeechRecognitionConstructor {
  new (): SpeechRecognition;
}

declare global {
  interface Window {
    SpeechRecognition: SpeechRecognitionConstructor;
    webkitSpeechRecognition: SpeechRecognitionConstructor;
  }
}
