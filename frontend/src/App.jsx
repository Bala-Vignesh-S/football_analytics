import { useState, useCallback, useRef } from 'react'

const API_BASE = '/api'

function App() {
  const [mode, setMode] = useState('image') // 'image' or 'video'
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  const fileInputRef = useRef(null)

  const acceptedFormats = mode === 'image'
    ? '.png,.jpg,.jpeg,.bmp,.webp'
    : '.mp4,.avi,.mov,.mkv,.webm'

  const formatLabel = mode === 'image'
    ? 'PNG, JPG, JPEG, BMP, WebP'
    : 'MP4, AVI, MOV, MKV, WebM'

  const handleFileSelect = useCallback((selectedFile) => {
    if (!selectedFile) return
    setFile(selectedFile)
    setResult(null)
    setError(null)
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile) handleFileSelect(droppedFile)
  }, [handleFileSelect])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setDragging(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setDragging(false)
  }, [])

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  const handleProcess = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const endpoint = mode === 'image' ? '/api/process-image' : '/api/process-video'

      const response = await fetch(endpoint, {
        method: 'POST',
        body: formData,
      })

      // Check response status BEFORE parsing JSON
      if (!response.ok) {
        let errorMessage = 'Processing failed'
        try {
          const errorData = await response.json()
          errorMessage = errorData.error || errorMessage
        } catch {
          // Response is not valid JSON
          errorMessage = `Server error (${response.status}): ${response.statusText}`
        }
        throw new Error(errorMessage)
      }

      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err.message || 'An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }

  const resetAll = () => {
    setFile(null)
    setResult(null)
    setError(null)
    setLoading(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <>
      {/* Header */}
      <header className="header">
        <div className="logo">
          <div className="logo-icon">⚽</div>
          <span className="logo-text">OffsideAI</span>
        </div>
        <div className="header-badge">🤖 Powered by YOLOv8</div>
      </header>

      {/* Hero */}
      <section className="hero">
        <h1>
          Detect <span className="highlight">Offside</span> Instantly
        </h1>
        <p>
          Upload a football match image or video and let our AI analyze player positions,
          detect teams, and draw the offside line in seconds.
        </p>
      </section>

      {/* Mode Toggle */}
      <div className="mode-toggle-container">
        <div className="mode-toggle">
          <button
            className={`mode-btn ${mode === 'image' ? 'active' : ''}`}
            onClick={() => { setMode('image'); resetAll() }}
          >
            🖼️ Image
          </button>
          <button
            className={`mode-btn ${mode === 'video' ? 'active' : ''}`}
            onClick={() => { setMode('video'); resetAll() }}
          >
            🎬 Video
          </button>
        </div>
      </div>

      {/* Main Content */}
      <main className="main-content">
        {/* Upload Zone */}
        {!loading && !result && (
          <>
            <div
              className={`upload-zone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
              onClick={() => fileInputRef.current?.click()}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept={acceptedFormats}
                onChange={(e) => handleFileSelect(e.target.files[0])}
                style={{ display: 'none' }}
              />

              {!file ? (
                <>
                  <span className="upload-icon">
                    {mode === 'image' ? '📸' : '🎥'}
                  </span>
                  <div className="upload-title">
                    Drop your {mode} here, or click to browse
                  </div>
                  <div className="upload-subtitle">
                    Select a football match {mode} for offside analysis
                  </div>
                  <div className="upload-formats">
                    Supported: {formatLabel}
                  </div>
                </>
              ) : (
                <>
                  <span className="upload-icon">✅</span>
                  <div className="upload-title">File Ready</div>
                  <div className="file-info" onClick={(e) => e.stopPropagation()}>
                    <span className="file-name">{file.name}</span>
                    <span className="file-size">{formatFileSize(file.size)}</span>
                    <button className="remove-file" onClick={(e) => { e.stopPropagation(); resetAll() }}>✕</button>
                  </div>
                </>
              )}
            </div>

            <button
              className="process-btn"
              disabled={!file}
              onClick={handleProcess}
            >
              {file ? `🚀 Analyze ${mode === 'image' ? 'Image' : 'Video'} for Offside` : `Select a ${mode} to begin`}
            </button>
          </>
        )}

        {/* Loading State */}
        {loading && (
          <div className="loading-container">
            <div className="spinner"></div>
            <div className="loading-text">
              <span className="loading-pulse">Analyzing {mode}...</span>
            </div>
            <div className="loading-sub">
              {mode === 'video'
                ? 'Processing frames with YOLOv8 — this may take a minute...'
                : 'Running player detection and offside computation...'}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="error-container">
            <span className="error-icon">⚠️</span>
            <span className="error-text">{error}</span>
          </div>
        )}

        {/* Results */}
        {result && (
          <section className="results-section">
            <div className="result-header">
              <h2 className="result-title">Analysis Results</h2>
              {result.info && (
                <span className={`result-badge ${result.info.offside_players > 0 ? 'offside' : 'no-offside'}`}>
                  {result.info.offside_players > 0
                    ? `🚩 ${result.info.offside_players} OFFSIDE`
                    : '✅ NO OFFSIDE'}
                </span>
              )}
              {result.info?.frames_with_offside !== undefined && (
                <span className={`result-badge ${result.info.frames_with_offside > 0 ? 'offside' : 'no-offside'}`}>
                  {result.info.frames_with_offside > 0
                    ? `🚩 Offside in ${result.info.frames_with_offside} frames`
                    : '✅ NO OFFSIDE'}
                </span>
              )}
            </div>

            {/* Image Result */}
            {result.image && (
              <div className="result-image-container">
                <img
                  src={result.image}
                  alt="Offside detection result"
                  className="result-image"
                />
              </div>
            )}

            {/* Video Result */}
            {result.video_url && (
              <video
                className="result-video"
                controls
                autoPlay
                muted
                src={result.video_url}
              />
            )}

            {/* Stats */}
            {result.info && (
              <div className="stats-grid">
                {result.info.players !== undefined && (
                  <div className="stat-card">
                    <div className="stat-value">{result.info.players}</div>
                    <div className="stat-label">Players</div>
                  </div>
                )}
                {result.info.goalkeepers !== undefined && (
                  <div className="stat-card">
                    <div className="stat-value">{result.info.goalkeepers}</div>
                    <div className="stat-label">Goalkeepers</div>
                  </div>
                )}
                {result.info.referees !== undefined && (
                  <div className="stat-card">
                    <div className="stat-value">{result.info.referees}</div>
                    <div className="stat-label">Referees</div>
                  </div>
                )}
                {result.info.balls !== undefined && (
                  <div className="stat-card">
                    <div className="stat-value">{result.info.balls}</div>
                    <div className="stat-label">Ball</div>
                  </div>
                )}
                {result.info.offside_players !== undefined && (
                  <div className="stat-card">
                    <div className="stat-value">{result.info.offside_players}</div>
                    <div className="stat-label">Offside</div>
                  </div>
                )}
                {result.info.total_frames !== undefined && (
                  <div className="stat-card">
                    <div className="stat-value">{result.info.total_frames}</div>
                    <div className="stat-label">Frames</div>
                  </div>
                )}
                {result.info.frames_with_offside !== undefined && (
                  <div className="stat-card">
                    <div className="stat-value">{result.info.frames_with_offside}</div>
                    <div className="stat-label">Offside Frames</div>
                  </div>
                )}
              </div>
            )}

            <button className="new-analysis-btn" onClick={resetAll}>
              ← New Analysis
            </button>
          </section>
        )}
      </main>
    </>
  )
}

export default App
