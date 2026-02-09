import { useState, useRef, useEffect, useCallback, memo } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  Send,
  Bot,
  User,
  Sparkles,
  Brain,
  Search,
  Database,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  sources?: Source[]
  toolCalls?: ToolCall[]
  isStreaming?: boolean
  isError?: boolean
}

interface Source {
  title: string
  snippet?: string
  score?: number
}

interface ToolCall {
  name: string
  type: 'cortex_analyst' | 'cortex_search' | 'custom'
  status: 'pending' | 'running' | 'complete' | 'error'
  sql?: string
  output?: any
  duration?: number
}

type ThinkingStage = 'idle' | 'classifying' | 'searching' | 'analyzing' | 'generating'

const SUGGESTED_QUESTIONS = [
  { text: 'Which assets need urgent maintenance?' },
  { text: 'What is the expected cost if AUTOCLAVE_01 fails?' },
  { text: 'Show me the highest risk assets' },
  { text: 'Compare PM cost vs unplanned failure cost' },
]

const AIThinking = memo(function AIThinking({
  stage,
  toolName,
}: {
  stage: ThinkingStage
  toolName?: string
}) {
  const stages = {
    idle: { icon: Brain, text: 'Ready', color: 'slate' },
    classifying: { icon: Brain, text: 'Understanding your question...', color: 'text-purple-400' },
    searching: {
      icon: Search,
      text: toolName ? `Searching ${toolName}...` : 'Searching knowledge base...',
      color: 'text-green-400',
    },
    analyzing: {
      icon: Database,
      text: toolName ? `Querying ${toolName}...` : 'Analyzing data...',
      color: 'text-blue-400',
    },
    generating: { icon: Sparkles, text: 'Generating response...', color: 'text-cyan-400' },
  }

  const current = stages[stage]
  const Icon = current.icon

  if (stage === 'idle') return null

  return (
    <div className="flex items-center gap-3 p-4">
      <div className="relative">
        <div className="w-10 h-10 rounded-xl bg-navy-600 flex items-center justify-center">
          <Icon size={20} className={current.color} />
        </div>
        <div className="absolute inset-0 bg-accent-blue/20 rounded-xl animate-ping" />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-medium ${current.color}`}>{current.text}</span>
          <div className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="w-1.5 h-1.5 bg-accent-blue rounded-full animate-bounce"
                style={{ animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
})

const ToolCallDisplay = memo(function ToolCallDisplay({
  toolCall,
  expanded,
  onToggle,
}: {
  toolCall: ToolCall
  expanded: boolean
  onToggle: () => void
}) {
  const Icon = toolCall.type === 'cortex_analyst' ? Database : Search

  return (
    <div className="mt-2 p-3 bg-navy-900/50 rounded-lg border border-navy-700">
      <button onClick={onToggle} className="w-full flex items-center gap-2 text-left">
        <Icon size={14} className="text-accent-blue" />
        <span className="text-xs text-slate-300 font-medium flex-1">{toolCall.name}</span>
        {toolCall.duration && <span className="text-xs text-slate-500">{toolCall.duration}ms</span>}
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {expanded && toolCall.sql && (
        <div className="mt-2">
          <p className="text-xs text-cyan-400 mb-1">SQL Query</p>
          <pre className="text-xs text-slate-400 font-mono bg-navy-950 p-2 rounded overflow-x-auto">
            {toolCall.sql}
          </pre>
        </div>
      )}
    </div>
  )
})

const SourcesDisplay = memo(function SourcesDisplay({ sources }: { sources: Source[] }) {
  if (!sources || sources.length === 0) return null
  return (
    <div className="mt-3 pt-3 border-t border-navy-600/50">
      <p className="text-xs text-slate-400 mb-2 flex items-center gap-1">
        <Search size={12} />
        Sources ({sources.length})
      </p>
      <div className="flex flex-wrap gap-1">
        {sources.map((source, i) => (
          <span
            key={i}
            className="text-xs px-2 py-1 bg-navy-600/50 text-accent-blue rounded-full"
            title={source.snippet}
          >
            {source.title}
          </span>
        ))}
      </div>
    </div>
  )
})

const MessageBubble = memo(function MessageBubble({ message }: { message: Message }) {
  const [copied, setCopied] = useState(false)
  const [expandedTool, setExpandedTool] = useState<number | null>(null)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''} animate-slide-up`}>
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
          message.role === 'user'
            ? 'bg-gradient-to-br from-accent-blue to-accent-blue/70'
            : 'bg-gradient-to-br from-navy-600 to-navy-700 ring-1 ring-navy-500'
        }`}
      >
        {message.role === 'user' ? (
          <User size={16} className="text-white" />
        ) : (
          <Sparkles size={16} className="text-accent-blue" />
        )}
      </div>

      <div
        className={`max-w-[80%] rounded-2xl p-4 group relative ${
          message.role === 'user'
            ? 'bg-gradient-to-br from-accent-blue to-accent-blue/80 text-white'
            : message.isError
              ? 'bg-red-900/30 text-red-200 ring-1 ring-red-700'
              : 'bg-navy-700/80 text-slate-200 ring-1 ring-navy-600'
        }`}
      >
        <div className="text-sm prose prose-invert prose-sm max-w-none
          prose-headings:text-slate-100 prose-headings:font-semibold prose-headings:mt-3 prose-headings:mb-2
          prose-h2:text-base prose-h3:text-sm
          prose-p:text-slate-200 prose-p:my-1.5 prose-p:leading-relaxed
          prose-strong:text-slate-100 prose-strong:font-semibold
          prose-ul:my-2 prose-ul:pl-4 prose-li:text-slate-200 prose-li:my-0.5
          prose-ol:my-2 prose-ol:pl-4
          prose-code:bg-navy-600 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-cyan-300 prose-code:text-xs prose-code:before:content-none prose-code:after:content-none
          prose-pre:bg-navy-900 prose-pre:p-3 prose-pre:rounded-lg prose-pre:overflow-x-auto
          prose-a:text-accent-blue prose-a:no-underline hover:prose-a:underline"
        >
          {message.role === 'user' ? (
            <p>{message.content}</p>
          ) : (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          )}
        </div>
        {message.isStreaming && (
          <span className="inline-block w-2 h-4 ml-1 bg-accent-blue animate-pulse rounded" />
        )}

        {message.role === 'assistant' && !message.isStreaming && (
          <button
            onClick={handleCopy}
            className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded hover:bg-navy-600"
            aria-label="Copy message"
          >
            {copied ? (
              <Check size={14} className="text-green-400" />
            ) : (
              <Copy size={14} className="text-slate-400" />
            )}
          </button>
        )}

        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-3 space-y-2">
            {message.toolCalls.map((tool, i) => (
              <ToolCallDisplay
                key={i}
                toolCall={tool}
                expanded={expandedTool === i}
                onToggle={() => setExpandedTool(expandedTool === i ? null : i)}
              />
            ))}
          </div>
        )}

        {message.sources && <SourcesDisplay sources={message.sources} />}
      </div>
    </div>
  )
})

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        "Hello! I'm your Snowcore Reliability Copilot. I can help you understand maintenance priorities, analyze asset risks, and make cost-effective decisions. What would you like to know?",
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [thinkingStage, setThinkingStage] = useState<ThinkingStage>('idle')

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      if (!input.trim() || isLoading) return

      const userMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content: input,
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, userMessage])
      setInput('')
      setIsLoading(true)
      setThinkingStage('classifying')

      const placeholderId = (Date.now() + 1).toString()
      setMessages((prev) => [
        ...prev,
        {
          id: placeholderId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          isStreaming: true,
        },
      ])

      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: input }),
        })

        const data = await response.json()

        setThinkingStage('generating')

        const fullText = data.response || data.content || ''
        const words = fullText.split(' ')
        let currentText = ''

        for (let i = 0; i < words.length; i++) {
          currentText += (i > 0 ? ' ' : '') + words[i]
          const textToShow = currentText

          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === placeholderId ? { ...msg, content: textToShow, isStreaming: i < words.length - 1 } : msg
            )
          )

          await new Promise((resolve) => setTimeout(resolve, 20))
        }

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === placeholderId
              ? {
                  ...msg,
                  content: fullText,
                  sources: data.sources,
                  toolCalls: data.tool_calls,
                  isStreaming: false,
                }
              : msg
          )
        )
      } catch (error) {
        console.error('Chat error:', error)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === placeholderId
              ? {
                  ...msg,
                  content: 'Sorry, I encountered an error. Please try again.',
                  isStreaming: false,
                  isError: true,
                }
              : msg
          )
        )
      } finally {
        setIsLoading(false)
        setThinkingStage('idle')
      }
    },
    [input, isLoading]
  )

  const handleSuggestionClick = (text: string) => {
    setInput(text)
    inputRef.current?.focus()
  }

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-navy-900 to-navy-800">
      <div className="p-4 border-b border-navy-700 bg-navy-800/50 backdrop-blur">
        <h2 className="font-semibold text-slate-200 flex items-center gap-2">
          <div className="relative">
            <Bot className="text-accent-blue" size={20} />
            <div className="absolute -top-1 -right-1 w-2 h-2 bg-accent-green rounded-full animate-pulse" />
          </div>
          Snowcore Reliability Copilot
          <span className="ml-auto text-xs text-slate-500 font-normal">Powered by Snowflake Cortex</span>
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {isLoading && thinkingStage !== 'idle' && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-navy-600 to-navy-700 ring-1 ring-navy-500 flex items-center justify-center">
              <Sparkles size={16} className="text-accent-blue" />
            </div>
            <div className="bg-navy-700/80 rounded-2xl ring-1 ring-navy-600 overflow-hidden">
              <AIThinking stage={thinkingStage} />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {messages.length <= 2 && (
        <div className="px-4 pb-2">
          <p className="text-xs text-slate-500 mb-2">Try asking:</p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED_QUESTIONS.map((q, i) => (
              <button
                key={i}
                onClick={() => handleSuggestionClick(q.text)}
                className="text-xs px-3 py-2 bg-navy-700/50 text-slate-300 rounded-full 
                         hover:bg-navy-600 hover:text-white transition-all duration-200
                         ring-1 ring-navy-600 hover:ring-accent-blue/50 flex items-center gap-1.5"
              >
                {q.text}
              </button>
            ))}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="p-4 border-t border-navy-700 bg-navy-800/50 backdrop-blur">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about maintenance priorities, asset risks, costs..."
            className="flex-1 bg-navy-700/50 border border-navy-600 rounded-xl px-4 py-3 
                     text-slate-200 placeholder-slate-500 
                     focus:outline-none focus:ring-2 focus:ring-accent-blue/50 focus:border-accent-blue
                     transition-all duration-200"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            aria-label="Send message"
            className="bg-gradient-to-r from-accent-blue to-accent-blue/80 
                     hover:from-accent-blue hover:to-accent-blue
                     disabled:from-navy-600 disabled:to-navy-600 disabled:cursor-not-allowed
                     text-white font-medium px-5 py-3 rounded-xl 
                     transition-all duration-200 flex items-center gap-2"
          >
            <Send size={18} />
          </button>
        </div>
      </form>
    </div>
  )
}
