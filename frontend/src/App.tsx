import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { 
  BookOpen, 
  Search, 
  Layers, 
  FileText, 
  Calendar, 
  MessageSquare, 
  Upload, 
  Mic, 
  Square, 
  Download, 
  Sparkles, 
  RefreshCw, 
  CheckCircle2, 
  AlertCircle,
  ExternalLink,
  Bot
} from 'lucide-react';

interface CourseListResponse {
  courses: string[];
}

interface SystemStatus {
  active_model: string;
  supported_models: string[];
  total_courses: number;
  courses: string[];
  persistent_storage: boolean;
}

interface SearchResult {
  course: string;
  topic: string;
  date: string;
  section: string;
  content: string;
}

interface Flashcard {
  course: string;
  file: string;
  question: string;
  answer: string;
}

interface ChatThread {
  session_id: string;
  first_message_time: string;
  message_count: number;
  preview: string;
  messages: Array<{
    role: string;
    message: string;
    created_at: string;
  }>;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'upload' | 'chat' | 'search' | 'flashcards' | 'cheatsheet' | 'recap'>('upload');
  const [courses, setCourses] = useState<string[]>([]);
  const [, setStatus] = useState<SystemStatus | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('gemini-3.6-flash');

  // Ingestion State
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [courseInput, setCourseInput] = useState('');
  const [topicInput, setTopicInput] = useState('');
  const [dateInput, setDateInput] = useState(new Date().toISOString().split('T')[0]);
  const [isDenseMath, setIsDenseMath] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [uploadResult, setUploadResult] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Audio Recording State
  const [isRecording, setIsRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const timerRef = useRef<any>(null);

  // Search State
  const [searchQuery, setSearchQuery] = useState('');
  const [searchCourseFilter, setSearchCourseFilter] = useState('All Courses');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  // Chat State
  const [chatCourse, setChatCourse] = useState('');
  const [chatPrompt, setChatPrompt] = useState('');
  const [chatHistory, setChatHistory] = useState<Array<{ role: string; content: string }>>([]);
  const [isChatting, setIsChatting] = useState(false);
  const [savedThreads, setSavedThreads] = useState<ChatThread[]>([]);
  const [historySearch, setHistorySearch] = useState('');

  // Flashcards State
  const [flashcards, setFlashcards] = useState<Flashcard[]>([]);
  const [cardIndex, setCardIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [flashcardCourse, setFlashcardCourse] = useState('All Courses');
  const [loadingCards, setLoadingCards] = useState(false);

  // Cheatsheet State
  const [csCourse, setCsCourse] = useState('');
  const [csContent, setCsContent] = useState('');
  const [isGeneratingCs, setIsGeneratingCs] = useState(false);

  // Recap State
  const [recapDate, setRecapDate] = useState(new Date().toISOString().split('T')[0]);
  const [recapContent, setRecapContent] = useState('');
  const [isGeneratingRecap, setIsGeneratingRecap] = useState(false);

  // Load initial courses & system status
  useEffect(() => {
    fetchCourses();
    fetchStatus();
    fetchSavedChats();
  }, []);

  const fetchCourses = async () => {
    try {
      const res = await fetch('/api/courses');
      const data: CourseListResponse = await res.json();
      setCourses(data.courses || []);
      if (data.courses?.length > 0) {
        setChatCourse(data.courses[0]);
        setCsCourse(data.courses[0]);
      }
    } catch (e) {
      console.error('Failed to load courses', e);
    }
  };

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/system_status');
      const data: SystemStatus = await res.json();
      setStatus(data);
      if (data.active_model) setSelectedModel(data.active_model);
    } catch (e) {
      console.error('Failed to load status', e);
    }
  };

  const fetchSavedChats = async (query: string = '') => {
    try {
      const url = query ? `/api/chat/history?search=${encodeURIComponent(query)}` : '/api/chat/history';
      const res = await fetch(url);
      const data = await res.json();
      setSavedThreads(data.threads || []);
    } catch (e) {
      console.error('Failed to load saved chats', e);
    }
  };

  // Auto-fill course/topic from file name
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setUploadFile(file);
      const name = file.name.replace(/\.[^/.]+$/, "");
      const parts = name.replace(/-/g, '_').split('_').filter(Boolean);
      
      const dateMatch = name.match(/(\d{4}[-_]\d{2}[-_]\d{2})/);
      if (dateMatch) {
        setDateInput(dateMatch[1].replace(/_/g, '-'));
      }

      if (!courseInput && parts.length > 0) {
        setCourseInput(parts[0]);
      }
      if (!topicInput && parts.length > 1) {
        setTopicInput(parts.slice(1).join(' '));
      } else if (!topicInput) {
        setTopicInput(name);
      }
    }
  };

  // Upload handler
  const handleProcessUpload = async () => {
    if (!uploadFile && !audioBlob) return;
    setIsProcessing(true);
    setUploadResult(null);
    setUploadError(null);

    const formData = new FormData();
    if (uploadFile) {
      formData.append('file', uploadFile);
    } else if (audioBlob) {
      formData.append('file', audioBlob, `recording_${Date.now()}.wav`);
    }

    formData.append('course_name', courseInput || 'General');
    formData.append('topic_name', topicInput || 'Lecture Ingestion');
    formData.append('lecture_date', dateInput);
    formData.append('model', selectedModel);
    formData.append('is_dense_math', String(isDenseMath));

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      
      const text = await res.text();
      let data: any = {};
      try {
        data = text ? JSON.parse(text) : {};
      } catch (jsonErr) {
        throw new Error(text || `Server returned HTTP ${res.status}`);
      }

      if (!res.ok) throw new Error(data.detail || data.message || `Upload failed with status ${res.status}`);
      setUploadResult(data.note_content);
      fetchCourses();
    } catch (err: any) {
      setUploadError(err.message || 'Error processing material');
    } finally {
      setIsProcessing(false);
    }
  };

  // Live Audio Recording
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: Blob[] = [];

      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: 'audio/wav' });
        setAudioBlob(blob);
      };

      recorder.start();
      setMediaRecorder(recorder);
      setIsRecording(true);
      setRecordingDuration(0);

      timerRef.current = setInterval(() => {
        setRecordingDuration((prev) => prev + 1);
      }, 1000);
    } catch (e) {
      alert('Microphone access denied or unsupported.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      mediaRecorder.stream.getTracks().forEach((t) => t.stop());
      setIsRecording(false);
      clearInterval(timerRef.current);
    }
  };

  // Semantic Search
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const url = `/api/search?q=${encodeURIComponent(searchQuery)}&course=${encodeURIComponent(searchCourseFilter)}`;
      const res = await fetch(url);
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch (e) {
      console.error(e);
    } finally {
      setIsSearching(false);
    }
  };

  // Chat Submission
  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatPrompt.trim()) return;

    const userMsg = chatPrompt;
    setChatPrompt('');
    setChatHistory((prev) => [...prev, { role: 'user', content: userMsg }]);
    setIsChatting(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          course: chatCourse,
          prompt: userMsg,
          model: selectedModel,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Chat query failed');
      setChatHistory((prev) => [...prev, { role: 'assistant', content: data.response }]);
      fetchSavedChats();
    } catch (err: any) {
      setChatHistory((prev) => [...prev, { role: 'assistant', content: `❌ Error: ${err.message}` }]);
    } finally {
      setIsChatting(false);
    }
  };

  // Flashcards Loader
  const loadFlashcards = async (course: string) => {
    setLoadingCards(true);
    try {
      const url = course === 'All Courses' ? '/api/flashcards' : `/api/flashcards?course=${encodeURIComponent(course)}`;
      const res = await fetch(url);
      const data = await res.json();
      setFlashcards(data.flashcards || []);
      setCardIndex(0);
      setIsFlipped(false);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingCards(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'flashcards') {
      loadFlashcards(flashcardCourse);
    }
  }, [activeTab, flashcardCourse]);

  // Cheatsheet Generator
  const handleGenerateCheatsheet = async () => {
    if (!csCourse) return;
    setIsGeneratingCs(true);
    try {
      const res = await fetch('/api/cheatsheet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course: csCourse, model: selectedModel }),
      });
      const data = await res.json();
      setCsContent(data.content || '');
    } catch (e) {
      alert('Error generating cheatsheet');
    } finally {
      setIsGeneratingCs(false);
    }
  };

  // Daily Recap Generator
  const handleGenerateRecap = async () => {
    setIsGeneratingRecap(true);
    try {
      const res = await fetch('/api/recap', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: recapDate, model: selectedModel }),
      });
      const data = await res.json();
      setRecapContent(data.content || '');
    } catch (e) {
      alert('Error generating recap');
    } finally {
      setIsGeneratingRecap(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      {/* Top Navbar */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-emerald-500/10 text-emerald-400 p-2 rounded-xl border border-emerald-500/20">
              <BookOpen className="w-6 h-6" />
            </div>
            <div>
              <h1 className="font-bold text-lg text-slate-100 flex items-center gap-2">
                Academic Assistant Hub
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                  FastAPI + React
                </span>
              </h1>
              <p className="text-xs text-slate-400">Autonomous Lecture Ingestion, KaTeX Derivations & Spaced Repetition</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 bg-slate-950/60 px-3 py-1.5 rounded-lg border border-slate-800 text-xs">
              <Bot className="w-4 h-4 text-emerald-400" />
              <span className="text-slate-400">Engine:</span>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="bg-transparent text-emerald-400 font-medium focus:outline-none cursor-pointer"
              >
                <option value="gemini-3.6-flash" className="bg-slate-900 text-slate-100">🧠 Auto: Tiered Routing (Recommended)</option>
                <option value="gemini-3.7-flash" className="bg-slate-900 text-slate-100">⚡ Gemini 3.7 Flash</option>
                <option value="gemini-3.6-flash" className="bg-slate-900 text-slate-100">⚡ Gemini 3.6 Flash (Audio & Math)</option>
                <option value="gemini-3.5-flash" className="bg-slate-900 text-slate-100">⚡ Gemini 3.5 Flash</option>
                <option value="gemini-3.0-flash" className="bg-slate-900 text-slate-100">⚡ Gemini 3.0 Flash</option>
                <option value="gemini-2.5-flash" className="bg-slate-900 text-slate-100">⚡ Gemini 2.5 Flash</option>
                <option value="gemini-3.5-flash-lite" className="bg-slate-900 text-slate-100">🚀 Gemini 3.5 Flash-Lite</option>
                <option value="gemini-3.1-flash-lite" className="bg-slate-900 text-slate-100">🚀 Gemini 3.1 Flash-Lite (Fast Slides/PDF)</option>
                <option value="gemini-2.5-flash-lite" className="bg-slate-900 text-slate-100">🚀 Gemini 2.5 Flash-Lite</option>
              </select>
            </div>

            <a
              href="https://t.me/abaja_note_taker_bot"
              target="_blank"
              rel="noreferrer"
              className="flex items-center space-x-1 text-xs bg-sky-500/10 text-sky-400 hover:bg-sky-500/20 border border-sky-500/30 px-3 py-1.5 rounded-lg transition"
            >
              <span>Telegram Bot</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </header>

      {/* Main Tab Navigation */}
      <div className="border-b border-slate-800 bg-slate-900/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex space-x-1 overflow-x-auto py-2">
          {[
            { id: 'upload', label: '📥 Lecture Ingestion', icon: Upload },
            { id: 'chat', label: '💬 Exam Tutor & Chat', icon: MessageSquare },
            { id: 'search', label: '🧠 Semantic Search', icon: Search },
            { id: 'flashcards', label: '📇 3D Flashcards & Anki', icon: Layers },
            { id: 'cheatsheet', label: '📋 Master Cheatsheet', icon: FileText },
            { id: 'recap', label: '📅 Daily Briefing', icon: Calendar },
          ].map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
                  active
                    ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Workspace View */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* ===================== TAB: UPLOAD / INGESTION ===================== */}
        {activeTab === 'upload' && (
          <div className="space-y-6">
            <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6">
              <h2 className="text-lg font-semibold text-slate-100 mb-1 flex items-center gap-2">
                <Upload className="w-5 h-5 text-emerald-400" />
                Ingest Lecture (Audio, Video, PDF, Slides & Docx)
              </h2>
              <p className="text-xs text-slate-400 mb-6">
                Auto-converts lectures to structured markdown notes, KaTeX equations, Mermaid diagrams, and syncs to Obsidian Git.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Course Name</label>
                  <input
                    type="text"
                    value={courseInput}
                    onChange={(e) => setCourseInput(e.target.value)}
                    placeholder="e.g. Machine Learning"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Topic Name</label>
                  <input
                    type="text"
                    value={topicInput}
                    onChange={(e) => setTopicInput(e.target.value)}
                    placeholder="e.g. Backpropagation & SGD"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Lecture Date</label>
                  <input
                    type="date"
                    value={dateInput}
                    onChange={(e) => setDateInput(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              {/* Upload Dropzone */}
              <div className="border-2 border-dashed border-slate-800 rounded-xl p-6 text-center hover:border-emerald-500/50 transition bg-slate-950/40 mb-6">
                <input
                  type="file"
                  id="file-upload"
                  className="hidden"
                  onChange={handleFileChange}
                  accept=".pdf,.docx,.doc,.txt,.md,.pptx,.ppt,.m4a,.mp3,.wav,.aac,.ogg,.flac"
                />
                <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center justify-center space-y-2">
                  <div className="p-3 bg-slate-800 rounded-full text-slate-300">
                    <Upload className="w-6 h-6" />
                  </div>
                  <span className="text-sm font-medium text-slate-200">
                    {uploadFile ? uploadFile.name : 'Choose a lecture file or drag & drop'}
                  </span>
                  <span className="text-xs text-slate-500">PDF, DOCX, PPTX, MP3, M4A, WAV up to 2GB</span>
                </label>
              </div>

              {/* Live Mic Recorder */}
              <div className="flex items-center justify-between bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 mb-6">
                <div className="flex items-center space-x-3">
                  <div className={`p-2 rounded-lg ${isRecording ? 'bg-rose-500/20 text-rose-400 animate-pulse' : 'bg-slate-800 text-slate-400'}`}>
                    <Mic className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="text-sm font-medium text-slate-200 block">Record In-Browser Audio</span>
                    <span className="text-xs text-slate-500">
                      {isRecording ? `Recording... ${recordingDuration}s` : audioBlob ? 'Audio note captured' : 'Capture live voice note'}
                    </span>
                  </div>
                </div>

                <div>
                  {!isRecording ? (
                    <button
                      onClick={startRecording}
                      className="px-4 py-1.5 rounded-lg text-xs font-medium bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 border border-rose-500/40 transition"
                    >
                      Start Mic
                    </button>
                  ) : (
                    <button
                      onClick={stopRecording}
                      className="px-4 py-1.5 rounded-lg text-xs font-medium bg-slate-800 text-slate-200 hover:bg-slate-700 flex items-center space-x-1 transition"
                    >
                      <Square className="w-3 h-3 text-rose-500" />
                      <span>Stop</span>
                    </button>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-between">
                <label className="flex items-center space-x-2 text-xs text-slate-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isDenseMath}
                    onChange={(e) => setIsDenseMath(e.target.checked)}
                    className="rounded border-slate-800 text-emerald-500 focus:ring-emerald-500"
                  />
                  <span>Dense Mathematical Derivations / Paper (Forces Deep Extraction)</span>
                </label>

                <button
                  onClick={handleProcessUpload}
                  disabled={isProcessing || (!uploadFile && !audioBlob)}
                  className="px-6 py-2.5 rounded-xl font-medium text-sm bg-emerald-500 text-slate-950 hover:bg-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 transition shadow-lg shadow-emerald-500/20"
                >
                  {isProcessing ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Analyzing with Gemini...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      <span>Process & Generate Notes</span>
                    </>
                  )}
                </button>
              </div>

              {uploadError && (
                <div className="mt-4 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm flex items-center space-x-2">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <span>{uploadError}</span>
                </div>
              )}
            </div>

            {uploadResult && (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
                <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
                  <h3 className="text-base font-semibold text-emerald-400 flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5" />
                    Generated Structured Academic Notes
                  </h3>
                </div>
                <div className="prose prose-invert max-w-none text-slate-300 text-sm leading-relaxed">
                  <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                    {uploadResult}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ===================== TAB: CHAT & EXAM TUTOR ===================== */}
        {activeTab === 'chat' && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Left Session Drawer */}
            <div className="lg:col-span-1 bg-slate-900/70 border border-slate-800 rounded-2xl p-4 flex flex-col h-[700px]">
              <div className="mb-3">
                <h3 className="text-sm font-semibold text-slate-200 mb-2">Saved Conversations</h3>
                <input
                  type="text"
                  value={historySearch}
                  onChange={(e) => {
                    setHistorySearch(e.target.value);
                    fetchSavedChats(e.target.value);
                  }}
                  placeholder="Search past chats..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="flex-1 overflow-y-auto space-y-2 pr-1">
                {savedThreads.length === 0 ? (
                  <p className="text-xs text-slate-500 text-center py-6">No saved conversations yet.</p>
                ) : (
                  savedThreads.map((t) => (
                    <div
                      key={t.session_id}
                      onClick={() => {
                        setChatHistory(t.messages.map((m) => ({ role: m.role, content: m.message })));
                      }}
                      className="p-3 bg-slate-950/60 hover:bg-slate-800/60 border border-slate-800/80 rounded-xl cursor-pointer transition text-xs"
                    >
                      <div className="font-medium text-slate-200 truncate">{t.preview}</div>
                      <div className="text-slate-500 mt-1 flex justify-between">
                        <span>{t.first_message_time.split('T')[0]}</span>
                        <span>{t.message_count} msgs</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Right Interactive Chat Panel */}
            <div className="lg:col-span-3 bg-slate-900/70 border border-slate-800 rounded-2xl p-6 flex flex-col h-[700px]">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                <div className="flex items-center space-x-3">
                  <span className="text-xs font-medium text-slate-400">Course Syllabus Filter:</span>
                  <select
                    value={chatCourse}
                    onChange={(e) => setChatCourse(e.target.value)}
                    className="bg-slate-950 border border-slate-800 text-emerald-400 text-xs rounded-lg px-3 py-1.5 focus:outline-none"
                  >
                    {courses.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>

                <button
                  onClick={() => setChatHistory([])}
                  className="text-xs text-slate-400 hover:text-slate-200 transition"
                >
                  Clear Screen
                </button>
              </div>

              {/* Chat Message Stream */}
              <div className="flex-1 overflow-y-auto space-y-4 pr-2 mb-4">
                {chatHistory.length === 0 ? (
                  <div className="text-center py-20 text-slate-500 space-y-2">
                    <MessageSquare className="w-8 h-8 mx-auto text-slate-600" />
                    <p className="text-sm font-medium">Ask any theorem, proof step, or exam concept doubt.</p>
                    <p className="text-xs text-slate-600">Full display LaTeX math will render below automatically.</p>
                  </div>
                ) : (
                  chatHistory.map((msg, i) => (
                    <div
                      key={i}
                      className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                    >
                      <div
                        className={`max-w-[85%] rounded-2xl p-4 text-sm leading-relaxed ${
                          msg.role === 'user'
                            ? 'bg-emerald-500/15 text-emerald-200 border border-emerald-500/30'
                            : 'bg-slate-950/80 text-slate-200 border border-slate-800/80 shadow-md'
                        }`}
                      >
                        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    </div>
                  ))
                )}
                {isChatting && (
                  <div className="flex items-center space-x-2 text-xs text-emerald-400">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Gemini is reasoning through lecture syllabus...</span>
                  </div>
                )}
              </div>

              {/* Chat Input Box */}
              <form onSubmit={handleSendChat} className="flex gap-2">
                <input
                  type="text"
                  value={chatPrompt}
                  onChange={(e) => setChatPrompt(e.target.value)}
                  placeholder="Ask a question or request step-by-step KaTeX derivation..."
                  className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                />
                <button
                  type="submit"
                  disabled={isChatting || !chatPrompt.trim()}
                  className="px-5 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-medium rounded-xl text-sm transition disabled:opacity-50"
                >
                  Send
                </button>
              </form>
            </div>
          </div>
        )}

        {/* ===================== TAB: SEMANTIC VECTOR SEARCH ===================== */}
        {activeTab === 'search' && (
          <div className="space-y-6">
            <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6">
              <h2 className="text-lg font-semibold text-slate-100 mb-1 flex items-center gap-2">
                <Search className="w-5 h-5 text-emerald-400" />
                Semester-Wide Semantic Vector Search (ChromaDB Hybrid RAG)
              </h2>
              <p className="text-xs text-slate-400 mb-6">
                Find exact mathematical derivations, concepts, and theorems across all recorded lectures.
              </p>

              <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3 mb-6">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="e.g. Find all proofs where Jensen's inequality or complementary slackness was used"
                  className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                />
                <select
                  value={searchCourseFilter}
                  onChange={(e) => setSearchCourseFilter(e.target.value)}
                  className="bg-slate-950 border border-slate-800 text-xs text-slate-300 rounded-xl px-4 py-2.5 focus:outline-none"
                >
                  <option value="All Courses">All Courses</option>
                  {courses.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
                <button
                  type="submit"
                  disabled={isSearching || !searchQuery.trim()}
                  className="px-6 py-2.5 bg-emerald-500 text-slate-950 font-medium rounded-xl text-sm hover:bg-emerald-400 transition disabled:opacity-50"
                >
                  {isSearching ? 'Searching...' : 'Search'}
                </button>
              </form>

              <div className="space-y-4">
                {searchResults.map((res, i) => (
                  <div key={i} className="bg-slate-950/70 border border-slate-800 rounded-xl p-5">
                    <div className="flex items-center justify-between text-xs text-emerald-400 font-medium mb-2">
                      <span>📌 [{res.course}] {res.topic} ({res.date})</span>
                      <span className="text-slate-500">{res.section}</span>
                    </div>
                    <div className="prose prose-invert max-w-none text-slate-300 text-sm">
                      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                        {res.content}
                      </ReactMarkdown>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ===================== TAB: 3D FLASHCARDS & ANKI ===================== */}
        {activeTab === 'flashcards' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between bg-slate-900/70 border border-slate-800 rounded-2xl p-4">
              <div className="flex items-center space-x-3">
                <span className="text-xs font-medium text-slate-400">Filter Deck:</span>
                <select
                  value={flashcardCourse}
                  onChange={(e) => setFlashcardCourse(e.target.value)}
                  className="bg-slate-950 border border-slate-800 text-emerald-400 text-xs rounded-lg px-3 py-1.5 focus:outline-none"
                >
                  <option value="All Courses">All Courses</option>
                  {courses.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>

              {flashcardCourse !== 'All Courses' && (
                <a
                  href={`/api/anki/download?course=${encodeURIComponent(flashcardCourse)}`}
                  className="flex items-center space-x-2 text-xs bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-3 py-1.5 rounded-lg hover:bg-emerald-500/25 transition"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download .apkg Deck</span>
                </a>
              )}
            </div>

            {loadingCards ? (
              <div className="text-center py-20 text-slate-500">Loading flashcard deck...</div>
            ) : flashcards.length === 0 ? (
              <div className="text-center py-20 text-slate-500">No flashcards found for this course.</div>
            ) : (
              <div className="flex flex-col items-center space-y-6">
                {/* 3D Flip Card Container */}
                <div
                  onClick={() => setIsFlipped(!isFlipped)}
                  className="w-full max-w-2xl h-80 perspective-1000 cursor-pointer"
                >
                  <div
                    className={`relative w-full h-full duration-500 transform-style-3d ${
                      isFlipped ? 'rotate-y-180' : ''
                    }`}
                  >
                    {/* Front: Question */}
                    <div className="absolute inset-0 bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800 rounded-3xl p-8 flex flex-col justify-between backface-hidden shadow-2xl">
                      <div className="flex justify-between text-xs text-slate-500">
                        <span>Card {cardIndex + 1} of {flashcards.length}</span>
                        <span className="text-emerald-400">Click to reveal answer</span>
                      </div>
                      <div className="text-lg font-medium text-slate-100 text-center">
                        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                          {flashcards[cardIndex]?.question}
                        </ReactMarkdown>
                      </div>
                      <div className="text-xs text-slate-600 text-center">Question</div>
                    </div>

                    {/* Back: Answer */}
                    <div className="absolute inset-0 bg-gradient-to-br from-slate-900 to-slate-950 border border-emerald-500/40 rounded-3xl p-8 flex flex-col justify-between backface-hidden rotate-y-180 shadow-2xl">
                      <div className="flex justify-between text-xs text-slate-500">
                        <span>Answer</span>
                        <span className="text-emerald-400">Click to flip back</span>
                      </div>
                      <div className="text-base text-slate-200 text-center overflow-y-auto pr-1">
                        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                          {flashcards[cardIndex]?.answer}
                        </ReactMarkdown>
                      </div>
                      <div className="text-xs text-slate-600 text-center">Verified Mathematical Concept</div>
                    </div>
                  </div>
                </div>

                {/* Card Controls */}
                <div className="flex items-center space-x-4">
                  <button
                    onClick={() => {
                      setIsFlipped(false);
                      setCardIndex((prev) => (prev > 0 ? prev - 1 : flashcards.length - 1));
                    }}
                    className="px-4 py-2 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-xs font-medium rounded-xl text-slate-300 transition"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setIsFlipped(!isFlipped)}
                    className="px-6 py-2 bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/25 text-xs font-medium rounded-xl transition"
                  >
                    Flip Card
                  </button>
                  <button
                    onClick={() => {
                      setIsFlipped(false);
                      setCardIndex((prev) => (prev < flashcards.length - 1 ? prev + 1 : 0));
                    }}
                    className="px-4 py-2 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-xs font-medium rounded-xl text-slate-300 transition"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ===================== TAB: CHEATSHEET ===================== */}
        {activeTab === 'cheatsheet' && (
          <div className="space-y-6">
            <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                    <FileText className="w-5 h-5 text-emerald-400" />
                    Master Exam Cheatsheet & Formula Reference
                  </h2>
                  <p className="text-xs text-slate-400">Synthesize all derivations and definitions into a 1-page formula reference sheet.</p>
                </div>
                <div className="flex items-center space-x-3">
                  <select
                    value={csCourse}
                    onChange={(e) => setCsCourse(e.target.value)}
                    className="bg-slate-950 border border-slate-800 text-emerald-400 text-xs rounded-xl px-4 py-2 focus:outline-none"
                  >
                    {courses.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <button
                    onClick={handleGenerateCheatsheet}
                    disabled={isGeneratingCs}
                    className="px-4 py-2 bg-emerald-500 text-slate-950 font-medium text-xs rounded-xl hover:bg-emerald-400 transition disabled:opacity-50"
                  >
                    {isGeneratingCs ? 'Synthesizing...' : 'Generate Sheet'}
                  </button>
                </div>
              </div>

              {csContent && (
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-6 mt-4 prose prose-invert max-w-none text-slate-300 text-sm">
                  <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                    {csContent}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ===================== TAB: RECAP ===================== */}
        {activeTab === 'recap' && (
          <div className="space-y-6">
            <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                    <Calendar className="w-5 h-5 text-emerald-400" />
                    Daily Multi-Subject Briefing
                  </h2>
                  <p className="text-xs text-slate-400">Generate executive summaries of all lectures recorded on a specific date.</p>
                </div>
                <div className="flex items-center space-x-3">
                  <input
                    type="date"
                    value={recapDate}
                    onChange={(e) => setRecapDate(e.target.value)}
                    className="bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded-xl px-3 py-2 focus:outline-none"
                  />
                  <button
                    onClick={handleGenerateRecap}
                    disabled={isGeneratingRecap}
                    className="px-4 py-2 bg-emerald-500 text-slate-950 font-medium text-xs rounded-xl hover:bg-emerald-400 transition disabled:opacity-50"
                  >
                    {isGeneratingRecap ? 'Generating...' : 'Generate Recap'}
                  </button>
                </div>
              </div>

              {recapContent && (
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-6 mt-4 prose prose-invert max-w-none text-slate-300 text-sm">
                  <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                    {recapContent}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
