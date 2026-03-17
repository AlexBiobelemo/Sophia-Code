# Version History

## v2.0.0 (2026-03-17) - Major AI Features Update

### 🎉 New Features

#### AI-Powered Code Generation
- **Streaming Code Generation**: Real-time code generation with typewriter effect
- **Modern UI Design**: Beautiful gradient backgrounds with micro-animations
- **Syntax Highlighting**: Prism.js integration for code blocks
- **Copy Functionality**: One-click copy for code and explanations
- **Save as Snippet**: Direct save generated code to snippets collection

#### AI Code Explanation
- **Formatted Explanations**: Markdown-rendered with proper typography
- **Copy Explanation**: Copy full explanation to clipboard
- **Apply to Description**: Replace snippet description with AI explanation
- **Enhanced Display**: Scrollable containers with custom styling

#### Smart Tag Suggestions
- **AI-Powered Tags**: Automatic tag generation from code analysis
- **Smart Filtering**: Extracts programming terms from AI responses
- **100+ Tag Vocabulary**: Recognizes languages, frameworks, concepts
- **Fallback Handling**: Graceful degradation on AI errors

#### Chat Assistant
- **Streaming Responses**: Real-time chat message streaming
- **Session Management**: Multiple chat conversations
- **Context-Aware**: Refers to user's snippets and solutions
- **CSRF Fixed**: Proper token handling for all endpoints

### 🐛 Bug Fixes

1. **Tag Generation**: Fixed AI returning explanations instead of tags
2. **Streaming Display**: Fixed code not displaying after generation
3. **CSRF Token Errors**: Fixed 400 errors on all AI endpoints
4. **Save Snippet Errors**: Fixed 400 errors when saving generated code
5. **Button Visibility**: Fixed invisible "Generate Code" button text

### 🎨 UI/UX Improvements

- Modern gradient backgrounds
- Glassmorphism effects
- Micro-animations (slide-up, checkmark pop, shimmer, ripple)
- Syntax-highlighted code blocks
- Custom scrollbars with blue accents
- Modern action buttons with gradients

### ⚙️ Technical Changes

- Removed MiniMax AI provider (Gemini-only)
- Added CSRF exemptions for 10 API endpoints
- Enhanced error handling and validation
- Improved streaming event handlers
- Production-ready configuration

### 📁 Files Added

- `app/static/css/ai-generation-modern.css` (500 lines)
- `app/static/css/streaming-output.css` (200 lines)
- `CHANGELOG.md`
- Database migrations

### 📁 Files Removed

- `app/ai_services_minimax.py`
- `minimax_api_fix.py`
- `enhanced_minimax_service.py`

---

## v1.x (Previous Versions)

See repository history for detailed version history.
