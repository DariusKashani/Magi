import React, { useState, useCallback, useEffect } from 'react';
import {
  Play, Book, Clock, CheckCircle, Loader, Download, Volume2,
  Search, Home, BookOpen, HelpCircle, User, Settings, Bell,
  ChevronRight, Star, Award, TrendingUp, Users, Calendar,
  MessageCircle, Target, Zap, FileText, Video, Headphones,
  ChevronDown, ArrowLeft
} from 'lucide-react';


//firebase import 
import { app, analytics } from './firebase';

// API Configuration
const API_BASE_URL = 'http://localhost:8000';

// MOVE VideoGeneratorPage OUTSIDE of the main component
const VideoGeneratorPage = ({ 
  formData, 
  setFormData, 
  error, 
  setError, 
  isGenerating, 
  setIsGenerating, 
  progress, 
  setProgress, 
  currentStep, 
  setCurrentStep, 
  generatedVideo, 
  setGeneratedVideo,
  backendConnected,
  setCurrentPage 
}) => {
  const [debugLogs, setDebugLogs] = useState([]);
  const [jobId, setJobId] = useState(null);
  const [showDebugMode, setShowDebugMode] = useState(false);
  
  const levelDescriptions = {
    1: { title: "Beginner", desc: "Perfect for those new to the topic", icon: "🌱" },
    2: { title: "Intermediate", desc: "Build on existing knowledge", icon: "🌿" },
    3: { title: "Advanced", desc: "Deep dive into complex concepts", icon: "🌳" }
  };

  // Enhanced logging
  const addDebugLog = (message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setDebugLogs(prev => [...prev.slice(-20), { // Keep last 20 logs
      time: timestamp,
      message,
      type
    }]);
    console.log(`[${timestamp}] ${message}`);
  };

  // Enhanced API functions with debugging
  const startVideoGeneration = async (videoRequest) => {
    addDebugLog(`🚀 Starting video generation with request: ${JSON.stringify(videoRequest)}`, 'info');
    
    const response = await fetch(`${API_BASE_URL}/api/generate-video`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(videoRequest),
    });

    addDebugLog(`📡 POST /api/generate-video response: ${response.status}`, response.ok ? 'success' : 'error');

    if (!response.ok) {
      const errorData = await response.json();
      addDebugLog(`❌ Error response: ${JSON.stringify(errorData)}`, 'error');
      throw new Error(errorData.detail || 'Failed to start video generation');
    }

    const result = await response.json();
    addDebugLog(`✅ Generation started: ${JSON.stringify(result)}`, 'success');
    return result;
  };

  const pollVideoStatus = async (jobId) => {
    addDebugLog(`📊 Polling status for job: ${jobId}`, 'info');
    
    const response = await fetch(`${API_BASE_URL}/api/video-status/${jobId}`);
    
    addDebugLog(`📡 GET /api/video-status/${jobId} response: ${response.status}`, response.ok ? 'success' : 'error');
    
    if (!response.ok) {
      const errorText = await response.text();
      addDebugLog(`❌ Status poll failed: ${errorText}`, 'error');
      throw new Error('Failed to get video status');
    }

    const result = await response.json();
    addDebugLog(`📈 Status update: ${JSON.stringify(result)}`, 'info');
    return result;
  };

  const checkAllJobs = async () => {
    try {
      addDebugLog('🔍 Fetching all jobs for debugging...', 'info');
      const response = await fetch(`${API_BASE_URL}/api/jobs`);
      if (response.ok) {
        const data = await response.json();
        addDebugLog(`📋 All jobs: ${JSON.stringify(data, null, 2)}`, 'info');
      }
    } catch (error) {
      addDebugLog(`❌ Failed to fetch jobs: ${error.message}`, 'error');
    }
  };

  const realVideoGeneration = async () => {
    setIsGenerating(true);
    setProgress(0);
    setError('');
    setGeneratedVideo(null);
    setDebugLogs([]); // Clear previous logs
    setJobId(null);
    
    try {
      const videoRequest = {
        topic: formData.topic,
        level: formData.level,
        duration: formData.duration,
        subtitle_style: formData.subtitleStyle,
        wpm: formData.wpm,
        dry_run: formData.dryRun
      };

      addDebugLog('🚀 Starting video generation process...', 'info');
      
      // Start video generation
      const startResponse = await startVideoGeneration(videoRequest);
      const currentJobId = startResponse.job_id;
      setJobId(currentJobId);
      
      addDebugLog(`✅ Job created with ID: ${currentJobId}`, 'success');

      // Poll for progress updates with enhanced error handling
      let pollCount = 0;
      let consecutiveErrors = 0;
      const maxConsecutiveErrors = 3;
      
      const pollInterval = setInterval(async () => {
        try {
          pollCount++;
          addDebugLog(`📊 Poll attempt ${pollCount} for job ${currentJobId}`, 'info');
          
          const status = await pollVideoStatus(currentJobId);
          consecutiveErrors = 0; // Reset error counter on success
          
          // Update UI state
          if (status.progress !== undefined) {
            setProgress(status.progress);
            addDebugLog(`Progress: ${status.progress}%`, 'success');
          }
          
          if (status.current_step) {
            setCurrentStep(status.current_step);
          }

          if (status.status === 'completed') {
            addDebugLog('🎉 Video generation completed!', 'success');
            clearInterval(pollInterval);
            
            setGeneratedVideo({
              title: formData.topic,
              duration: `${formData.duration}:00`,
              jobId: currentJobId,
              downloadUrl: `${API_BASE_URL}/api/video/${currentJobId}`,
              status: 'completed'
            });
            
            setCurrentStep("Video ready for download!");
            setProgress(100);
            setIsGenerating(false);
            
          } else if (status.status === 'failed') {
            addDebugLog(`❌ Video generation failed: ${status.error}`, 'error');
            clearInterval(pollInterval);
            throw new Error(status.error || 'Video generation failed');
          }
          
          // Log if taking a long time
          if (pollCount === 10) {
            addDebugLog('⏰ Generation taking longer than expected (30s), but continuing...', 'warning');
          } else if (pollCount === 40) {
            addDebugLog('⏰ Generation taking much longer than expected (2min), checking all jobs...', 'warning');
            await checkAllJobs();
          }
          
        } catch (pollError) {
          consecutiveErrors++;
          addDebugLog(`🚨 Poll error ${consecutiveErrors}/${maxConsecutiveErrors}: ${pollError.message}`, 'error');
          
          // If too many consecutive errors, fail
          if (consecutiveErrors >= maxConsecutiveErrors) {
            clearInterval(pollInterval);
            throw new Error(`Polling failed after ${maxConsecutiveErrors} consecutive errors: ${pollError.message}`);
          }
          
          // Otherwise, continue polling
        }
      }, 3000); // Poll every 3 seconds

      // Extended timeout with warning
      setTimeout(() => {
        if (pollInterval) {
          addDebugLog('⏰ 15 minute timeout reached', 'warning');
          clearInterval(pollInterval);
          if (isGenerating) {
            setError('Video generation timed out after 15 minutes. The video might still be processing. Check back later.');
            setIsGenerating(false);
          }
        }
      }, 900000); // 15 minute timeout
        
    } catch (err) {
      addDebugLog(`💥 Generation failed: ${err.message}`, 'error');
      setError(err.message || "Failed to generate video. Please try again.");
      setIsGenerating(false);
    }
  };

  const handleSubmit = async () => {
    if (!formData.topic.trim()) {
      setError("Please enter a topic for your video");
      return;
    }
    
    if (!backendConnected) {
      setError("Backend is not connected. Please make sure the API server is running.");
      return;
    }
    
    realVideoGeneration();
  };

  const handleInputChange = useCallback((field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setError('');
  }, [setFormData, setError]);

  const handleDownload = () => {
    if (generatedVideo && generatedVideo.downloadUrl) {
      const link = document.createElement('a');
      link.href = generatedVideo.downloadUrl;
      link.download = `magi_video_${generatedVideo.jobId}.mp4`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  // Test functions for debugging
  const testBackendConnection = async () => {
    try {
      addDebugLog('🔍 Testing backend connection...', 'info');
      const response = await fetch(`${API_BASE_URL}/health`);
      const data = await response.json();
      addDebugLog(`✅ Backend health: ${JSON.stringify(data)}`, 'success');
    } catch (error) {
      addDebugLog(`❌ Backend connection failed: ${error.message}`, 'error');
    }
  };

  // Debug panel component
  const DebugPanel = () => (
    <div className="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-xs max-h-96 overflow-y-auto">
      <div className="flex justify-between items-center mb-2">
        <span className="text-green-300 font-bold">Debug Console</span>
        <button 
          onClick={() => setDebugLogs([])}
          className="text-red-400 hover:text-red-300"
        >
          Clear
        </button>
      </div>
      
      {jobId && (
        <div className="mb-2 p-2 bg-blue-900/50 rounded">
          <span className="text-blue-300">Current Job ID: {jobId}</span>
        </div>
      )}
      
      <div className="space-y-1">
        {debugLogs.map((log, index) => (
          <div key={index} className={`${
            log.type === 'error' ? 'text-red-400' :
            log.type === 'success' ? 'text-green-400' :
            log.type === 'warning' ? 'text-yellow-400' :
            'text-gray-300'
          }`}>
            <span className="text-gray-500">[{log.time}]</span> {log.message}
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <button 
        onClick={() => setCurrentPage('home')}
        className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 mb-6 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Home</span>
      </button>

      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">AI Educational Video Generator</h1>
            <p className="text-gray-600">Create personalized learning content powered by advanced AI</p>
          </div>
          <button
            onClick={() => setShowDebugMode(!showDebugMode)}
            className="bg-gray-600 hover:bg-gray-700 text-white text-sm px-3 py-2 rounded-lg"
          >
            {showDebugMode ? 'Hide' : 'Show'} Debug
          </button>
        </div>
        
        {/* Backend Connection Status */}
        <div className="mt-4 flex items-center space-x-4">
          <div className={`inline-flex items-center space-x-2 px-3 py-2 rounded-lg text-sm ${
            backendConnected 
              ? 'bg-green-50 text-green-700 border border-green-200' 
              : 'bg-red-50 text-red-700 border border-red-200'
          }`}>
            <div className={`w-2 h-2 rounded-full ${backendConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
            <span>
              {backendConnected ? 'Connected to video generation service' : 'Disconnected from backend service'}
            </span>
          </div>
          
          {showDebugMode && (
            <div className="flex space-x-2">
              <button
                onClick={testBackendConnection}
                className="bg-blue-100 text-blue-700 text-xs px-2 py-1 rounded"
              >
                Test Connection
              </button>
              <button
                onClick={() => checkAllJobs()}
                className="bg-purple-100 text-purple-700 text-xs px-2 py-1 rounded"
              >
                List Jobs
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        {/* Form */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <div className="space-y-6">
              {/* Topic Input */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  What would you like to learn?
                </label>
                <textarea
                  value={formData.topic}
                  onChange={(e) => handleInputChange('topic', e.target.value)}
                  placeholder="e.g., Teach me what a derivative is, Explain photosynthesis, How does machine learning work?"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                  rows={3}
                  disabled={isGenerating}
                />
              </div>

              {/* Level Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Learning Level
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {Object.entries(levelDescriptions).map(([level, info]) => (
                    <button
                      key={level}
                      onClick={() => handleInputChange('level', parseInt(level))}
                      disabled={isGenerating}
                      className={`p-3 rounded-lg border-2 text-center transition-all ${
                        formData.level === parseInt(level)
                          ? 'border-blue-500 bg-blue-50 text-blue-700'
                          : 'border-gray-200 hover:border-gray-300 text-gray-600'
                      }`}
                    >
                      <div className="text-lg mb-1">{info.icon}</div>
                      <div className="text-sm font-medium">{info.title}</div>
                      <div className="text-xs text-gray-500 mt-1">{info.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Duration */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Video Duration
                </label>
                <div className="flex items-center space-x-4">
                  <Clock className="w-5 h-5 text-gray-400" />
                  <input
                    type="range"
                    min="2"
                    max="15"
                    value={formData.duration}
                    onChange={(e) => handleInputChange('duration', parseInt(e.target.value))}
                    disabled={isGenerating}
                    className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                  />
                  <span className="text-sm font-medium text-gray-600 min-w-[4rem]">
                    {formData.duration} min{formData.duration !== 1 ? 's' : ''}
                  </span>
                </div>
              </div>

              {/* Advanced Options */}
              <details className="group">
                <summary className="cursor-pointer text-sm font-medium text-gray-700 flex items-center space-x-2">
                  <span>Advanced Options</span>
                  <span className="transform group-open:rotate-90 transition-transform">▶</span>
                </summary>
                
                <div className="mt-4 space-y-4 pl-4 border-l-2 border-gray-100">
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      id="dryRun"
                      checked={formData.dryRun}
                      onChange={(e) => handleInputChange('dryRun', e.target.checked)}
                      disabled={isGenerating}
                      className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <label htmlFor="dryRun" className="text-sm text-gray-700">
                      Preview mode (faster generation, no audio)
                    </label>
                  </div>
                </div>
              </details>

              <button
                onClick={handleSubmit}
                disabled={isGenerating || !formData.topic.trim() || !backendConnected}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium py-3 px-6 rounded-lg transition-colors flex items-center justify-center space-x-2"
              >
                {isGenerating ? (
                  <>
                    <Loader className="w-5 h-5 animate-spin" />
                    <span>Generating Video...</span>
                  </>
                ) : !backendConnected ? (
                  <>
                    <span>Backend Disconnected</span>
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5" />
                    <span>Generate Video</span>
                  </>
                )}
              </button>

              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Progress & Results */}
        <div className="space-y-6">
          {isGenerating && (
            <div className="bg-white rounded-xl shadow-sm border p-6">
              <div className="flex items-center space-x-2 mb-4">
                <Loader className="w-5 h-5 text-blue-600 animate-spin" />
                <h3 className="text-lg font-semibold text-gray-900">Creating Your Video</h3>
              </div>
              
              <div className="space-y-4">
                <div className="bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">{currentStep}</span>
                  <span className="text-blue-600 font-medium">{Math.round(progress)}%</span>
                </div>
              </div>
            </div>
          )}

          {generatedVideo && (
            <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
              <div className="aspect-video bg-gray-900 relative group">
                {/* Video Player */}
                <video
                  className="w-full h-full object-cover"
                  controls
                  preload="metadata"
                  poster={generatedVideo.thumbnailUrl || undefined}
                  onError={(e) => {
                    console.error('Video playback error:', e);
                    // Show fallback if video fails to load
                    e.target.style.display = 'none';
                    e.target.nextSibling.style.display = 'flex';
                  }}
                >
                  <source src={generatedVideo.downloadUrl} type="video/mp4" />
                  Your browser does not support the video tag.
                </video>
                
                {/* Fallback display if video fails */}
                <div className="w-full h-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center hidden">
                  <div className="text-center text-white">
                    <Video className="w-16 h-16 mx-auto mb-4" />
                    <p className="text-lg font-medium">Video Ready for Download!</p>
                    <p className="text-sm opacity-80">Playback not available</p>
                  </div>
                </div>
                
                {/* Download overlay (appears on hover) */}
                <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button 
                    onClick={handleDownload}
                    className="bg-black bg-opacity-50 hover:bg-opacity-70 text-white rounded-full p-2 transition-all"
                    title="Download Video"
                  >
                    <Download className="w-5 h-5" />
                  </button>
                </div>
                
                {/* Video loading overlay */}
                <div className="absolute inset-0 bg-black bg-opacity-20 flex items-center justify-center pointer-events-none">
                  <div className="bg-black bg-opacity-50 text-white px-3 py-1 rounded-full text-sm opacity-0 group-hover:opacity-100 transition-opacity">
                    Click to play your video!
                  </div>
                </div>
              </div>
              
              <div className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                      {generatedVideo.title}
                    </h3>
                    
                    <div className="flex items-center space-x-4 text-sm text-gray-600">
                      <div className="flex items-center space-x-1">
                        <Clock className="w-4 h-4" />
                        <span>{generatedVideo.duration}</span>
                      </div>
                      <div className="flex items-center space-x-1">
                        <Volume2 className="w-4 h-4" />
                        <span>Audio Included</span>
                      </div>
                      <div className="flex items-center space-x-1">
                        <Play className="w-4 h-4 text-green-600" />
                        <span className="text-green-600 font-medium">Ready to Watch</span>
                      </div>
                      {generatedVideo.thumbnailUrl && (
                        <div className="flex items-center space-x-1">
                          <span className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded">
                            🎨 AI Thumbnail
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* Quick actions */}
                  <div className="flex space-x-2">
                    <button 
                      onClick={handleDownload}
                      className="bg-blue-100 hover:bg-blue-200 text-blue-700 p-2 rounded-lg transition-colors"
                      title="Download Video"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                
                {/* Action buttons */}
                <div className="flex space-x-3">
                  <button 
                    onClick={() => {
                      // Restart video playback
                      const video = document.querySelector('video');
                      if (video) {
                        video.currentTime = 0;
                        video.play();
                      }
                    }}
                    className="flex-1 bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center space-x-2"
                  >
                    <Play className="w-4 h-4" />
                    <span>Watch Video</span>
                  </button>
                  
                  <button 
                    onClick={handleDownload}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center space-x-2"
                  >
                    <Download className="w-4 h-4" />
                    <span>Download</span>
                  </button>
                  
                  <button 
                    onClick={() => {
                      setGeneratedVideo(null);
                      setFormData(prev => ({ ...prev, topic: '' }));
                    }}
                    className="bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium py-2 px-4 rounded-lg transition-colors"
                  >
                    Create Another
                  </button>
                </div>
                
                {/* Video info */}
                <div className="mt-4 pt-4 border-t border-gray-100">
                  <div className="text-sm text-gray-500">
                    💡 <strong>Tip:</strong> Right-click the video to save, share, or view in fullscreen
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Debug Panel */}
          {showDebugMode && (
            <DebugPanel />
          )}

          {/* Info Panel */}
          <div className="bg-blue-50 rounded-xl border border-blue-200 p-6">
            <h3 className="text-lg font-semibold text-blue-900 mb-3">How Magi works</h3>
            <div className="space-y-3 text-sm text-blue-800">
              <div className="flex items-start space-x-2">
                <CheckCircle className="w-4 h-4 mt-0.5 text-blue-600" />
                <span>AI generates a detailed educational script</span>
              </div>
              <div className="flex items-start space-x-2">
                <CheckCircle className="w-4 h-4 mt-0.5 text-blue-600" />
                <span>Mathematical animations created with Manim</span>
              </div>
              <div className="flex items-start space-x-2">
                <CheckCircle className="w-4 h-4 mt-0.5 text-blue-600" />
                <span>Professional narration with ElevenLabs AI</span>
              </div>
              <div className="flex items-start space-x-2">
                <CheckCircle className="w-4 h-4 mt-0.5 text-blue-600" />
                <span>Synchronized subtitles and final assembly</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Main App Component
const KhanAcademyApp = () => {
  const [currentPage, setCurrentPage] = useState('home');
  const [searchQuery, setSearchQuery] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState('');
  const [generatedVideo, setGeneratedVideo] = useState(null);
  const [error, setError] = useState('');
  const [showExploreDropdown, setShowExploreDropdown] = useState(false);
  const [backendConnected, setBackendConnected] = useState(false);

  const [formData, setFormData] = useState({
    topic: '',
    level: 2,
    duration: 5,
    subtitleStyle: 'modern',
    wpm: 150,
    dryRun: false
  });

  // Check backend health on component mount
  useEffect(() => {
    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const checkBackendHealth = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/health`);
      setBackendConnected(response.ok);
      return response.ok;
    } catch (error) {
      setBackendConnected(false);
      return false;
    }
  };

  // Sample data
  const exploreCategories = [
    {
      title: "Math",
      icon: "📊",
      subcategories: [
        "Pre-K through grade 2 (Magi Kids)",
        "Early math review",
        "2nd grade",
        "3rd grade",
        "4th grade",
        "5th grade",
        "7th grade",
        "8th grade",
        "Algebra basics",
        "Calculus",
        "Statistics"
      ]
    },
    {
      title: "Science",
      icon: "🔬",
      subcategories: [
        "Biology",
        "Chemistry",
        "Physics",
        "Earth and space science",
        "AP Biology",
        "AP Chemistry",
        "AP Physics 1"
      ]
    },
    {
      title: "Computing",
      icon: "💻",
      subcategories: [
        "Intro to CS - Python",
        "Computer programming",
        "Pixar in a Box",
        "Computers and the Internet"
      ]
    },
    {
      title: "Test prep",
      icon: "📝",
      subcategories: [
        "Digital SAT",
        "LSAT",
        "Get ready for SAT Prep: Math",
        "MCAT"
      ]
    },
    {
      title: "Arts & humanities",
      icon: "🎨",
      subcategories: [
        "World history",
        "US history",
        "Art history",
        "Grammar"
      ]
    },
    {
      title: "Economics & finance",
      icon: "💰",
      subcategories: [
        "Microeconomics",
        "Macroeconomics",
        "Personal finance"
      ]
    }
  ];

  const sampleVideos = [
    { id: 1, title: "Introduction to Derivatives", duration: "8:42", views: "2.1M", thumbnail: "🔢" },
    { id: 2, title: "Understanding Photosynthesis", duration: "12:15", views: "1.8M", thumbnail: "🌱" },
    { id: 3, title: "Linear Algebra Basics", duration: "15:30", views: "956K", thumbnail: "📐" },
    { id: 4, title: "Chemical Bonding Explained", duration: "10:22", views: "743K", thumbnail: "⚛️" },
    { id: 5, title: "World War II Timeline", duration: "18:45", views: "1.2M", thumbnail: "🌍" },
  ];

  const courses = [
    { id: 1, title: "Calculus", description: "Master derivatives, integrals, and more", lessons: 45, progress: 67, difficulty: "Advanced", color: "bg-blue-500" },
    { id: 2, title: "Biology", description: "Explore life sciences and organisms", lessons: 38, progress: 23, difficulty: "Intermediate", color: "bg-green-500" },
    { id: 3, title: "Physics", description: "Understand motion, energy, and forces", lessons: 52, progress: 89, difficulty: "Advanced", color: "bg-purple-500" },
    { id: 4, title: "Chemistry", description: "Learn about atoms, molecules, and reactions", lessons: 41, progress: 12, difficulty: "Intermediate", color: "bg-red-500" },
    { id: 5, title: "History", description: "Journey through human civilization", lessons: 33, progress: 45, difficulty: "Beginner", color: "bg-yellow-500" },
    { id: 6, title: "Statistics", description: "Data analysis and probability", lessons: 29, progress: 78, difficulty: "Intermediate", color: "bg-indigo-500" },
  ];

  const Navigation = () => (
    <nav className="bg-white shadow-sm border-b sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex items-center justify-between h-16">
          {/* Left side - Explore + Logo */}
          <div className="flex items-center space-x-6">
            {/* Explore Dropdown */}
            <div className="relative">
              <button
                onClick={() => setShowExploreDropdown(!showExploreDropdown)}
                onBlur={() => setTimeout(() => setShowExploreDropdown(false), 150)}
                className="flex items-center space-x-1 px-3 py-2 text-gray-700 hover:text-gray-900 font-medium"
              >
                <span>Explore</span>
                <ChevronRight className={`w-4 h-4 transition-transform ${showExploreDropdown ? 'rotate-90' : ''}`} />
              </button>
             
              {showExploreDropdown && (
                <div className="absolute top-full left-0 mt-1 w-80 bg-white rounded-lg shadow-lg border border-gray-200 py-4 z-50">
                  <div className="max-h-96 overflow-y-auto">
                    {exploreCategories.map((category, index) => (
                      <div key={index} className="px-4 py-2">
                        <div className="flex items-center space-x-2 font-medium text-gray-900 mb-2">
                          <span className="text-lg">{category.icon}</span>
                          <span>{category.title}</span>
                        </div>
                        <div className="ml-6 space-y-1">
                          {category.subcategories.slice(0, 4).map((sub, subIndex) => (
                            <button
                              key={subIndex}
                              onClick={() => {
                                setCurrentPage('courses');
                                setShowExploreDropdown(false);
                              }}
                              className="block text-sm text-gray-600 hover:text-blue-600 py-1"
                            >
                              {sub}
                            </button>
                          ))}
                          {category.subcategories.length > 4 && (
                            <button
                              onClick={() => {
                                setCurrentPage('courses');
                                setShowExploreDropdown(false);
                              }}
                              className="text-sm text-blue-600 hover:text-blue-700 py-1"
                            >
                              View all {category.title.toLowerCase()}
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Search Bar */}
            <div className="relative w-96">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Center - Logo */}
          <div className="flex items-center space-x-3">
            <button
              onClick={() => setCurrentPage('home')}
              className="flex items-center space-x-3 hover:opacity-80 transition-opacity"
            >
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <Play className="w-4 h-4 text-white" />
              </div>
              <span className="text-xl font-bold text-gray-900">Magi</span>
            </button>
          </div>

          {/* Right side - Navigation + User */}
          <div className="flex items-center space-x-6">
            {/* Main Navigation Links */}
            <div className="hidden md:flex items-center space-x-6">
              <button
                onClick={() => setCurrentPage('generator')}
                className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-colors text-sm font-medium ${
                  currentPage === 'generator' ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                AI Video Generator
                <span className="bg-blue-100 text-blue-700 text-xs px-2 py-1 rounded-full ml-1">NEW</span>
              </button>
              <button
                onClick={() => setCurrentPage('help')}
                className={`px-3 py-2 rounded-lg transition-colors text-sm font-medium ${
                  currentPage === 'help' ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                For Teachers
                <span className="bg-green-100 text-green-700 text-xs px-2 py-1 rounded-full ml-1">FREE</span>
              </button>
              <button className="text-blue-600 hover:text-blue-700 text-sm font-medium">
                Donate
              </button>
            </div>

            {/* User Menu */}
            <div className="flex items-center space-x-3">
              <button className="text-blue-600 hover:text-blue-700 text-sm font-medium">
                Log in
              </button>
              <button className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
                Sign up
              </button>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );

  const BackButton = () => (
    <button
      onClick={() => setCurrentPage('home')}
      className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 mb-6 transition-colors"
    >
      <ArrowLeft className="w-4 h-4" />
      <span>Back to Home</span>
    </button>
  );

  const HomePage = () => (
    <div className="max-w-7xl mx-auto px-6 py-8">
      {/* Hero Section - AI Video Generator */}
      <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-2xl p-8 mb-12">
        <div className="grid lg:grid-cols-2 gap-8 items-center">
          <div>
            <h1 className="text-4xl font-bold text-gray-900 mb-4">
              Meet Magi: AI tutor for learners, sidekick for teachers.
            </h1>
            <p className="text-lg text-gray-600 mb-6">
              Magi moves the needle for educators and students. Powered by advanced AI,
              Magi delivers personalized educational videos tailored to your teaching and learning experience!
            </p>
            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => setCurrentPage('generator')}
                className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-3 rounded-lg transition-colors"
              >
                AI Video Generator
              </button>
              <button
                onClick={() => setCurrentPage('help')}
                className="border border-blue-600 text-blue-600 hover:bg-blue-50 font-medium px-6 py-3 rounded-lg transition-colors"
              >
                For Learners
              </button>
            </div>
          </div>
          <div className="relative">
            {/* AI Avatar Illustration */}
            <div className="w-80 h-80 mx-auto relative">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-400 to-purple-500 rounded-full"></div>
              <div className="absolute inset-4 bg-white rounded-full flex items-center justify-center">
                <div className="text-6xl">🤖</div>
              </div>
              {/* Chat bubbles */}
              <div className="absolute -top-4 -left-4 bg-yellow-200 rounded-2xl p-3 shadow-lg">
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                </div>
              </div>
              <div className="absolute top-8 -right-8 bg-purple-200 rounded-2xl p-3 shadow-lg">
                <span className="text-sm font-medium">How can I help?</span>
              </div>
              <div className="absolute -bottom-4 -right-4 bg-blue-200 rounded-2xl p-3 shadow-lg">
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Subject Categories - Khan Academy Style */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {exploreCategories.map((category, index) => (
          <div key={index} className="bg-white rounded-xl border border-gray-200 hover:shadow-lg transition-shadow">
            <button
              onClick={() => setCurrentPage('courses')}
              className="w-full p-6 text-left"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <div className="w-12 h-12 bg-orange-100 rounded-xl flex items-center justify-center text-2xl">
                    {category.icon}
                  </div>
                  <span className="text-lg font-semibold text-gray-900">{category.title}</span>
                </div>
                <ChevronRight className="w-5 h-5 text-gray-400" />
              </div>
             
              <div className="space-y-2">
                {category.subcategories.slice(0, 3).map((sub, subIndex) => (
                  <div key={subIndex} className="text-sm text-gray-600 flex items-center space-x-2">
                    <span>{sub}</span>
                  </div>
                ))}
                {category.subcategories.length > 3 && (
                  <div className="text-sm text-blue-600 font-medium">
                    +{category.subcategories.length - 3} more
                  </div>
                )}
              </div>
            </button>
          </div>
        ))}
      </div>
    </div>
  );

  const CoursesPage = () => (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <BackButton />
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Courses</h1>
        <p className="text-gray-600">Structured learning paths to master any subject</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-8">
        <button className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium">All</button>
        <button className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">Math</button>
        <button className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">Science</button>
        <button className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">History</button>
        <button className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">Computer Science</button>
      </div>

      {/* Course Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {courses.map(course => (
          <div key={course.id} className="bg-white rounded-xl shadow-sm border hover:shadow-lg transition-shadow">
            <div className={`h-32 ${course.color} rounded-t-xl flex items-center justify-center`}>
              <Book className="w-8 h-8 text-white" />
            </div>
            <div className="p-6">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-semibold text-gray-900">{course.title}</h3>
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">{course.difficulty}</span>
              </div>
              <p className="text-gray-600 mb-4">{course.description}</p>
             
              <div className="mb-4">
                <div className="flex justify-between text-sm text-gray-600 mb-1">
                  <span>Progress</span>
                  <span>{course.progress}%</span>
                </div>
                <div className="bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all"
                    style={{ width: `${course.progress}%` }}
                  />
                </div>
              </div>
             
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">{course.lessons} lessons</span>
                <button className="text-blue-600 hover:text-blue-700 font-medium flex items-center space-x-1">
                  <span>Continue</span>
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const HelpPage = () => {
    const [problemType, setProblemType] = useState('');
    const [problemText, setProblemText] = useState('');
    const [subject, setSubject] = useState('');

    return (
      <div className="max-w-4xl mx-auto px-6 py-8">
        <BackButton />
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Get Help</h1>
          <p className="text-gray-600">Solve specific problems with step-by-step guidance</p>
        </div>

        <div className="grid md:grid-cols-2 gap-8">
          {/* Problem Input */}
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Describe Your Problem</h2>
           
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Subject</label>
                <select
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select a subject</option>
                  <option value="math">Mathematics</option>
                  <option value="physics">Physics</option>
                  <option value="chemistry">Chemistry</option>
                  <option value="biology">Biology</option>
                  <option value="history">History</option>
                  <option value="english">English</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Problem Type</label>
                <div className="grid grid-cols-2 gap-2">
                  {['Homework', 'Concept', 'Practice', 'Test Prep'].map(type => (
                    <button
                      key={type}
                      onClick={() => setProblemType(type)}
                      className={`p-2 text-sm rounded-lg border transition-colors ${
                        problemType === type
                          ? 'border-blue-500 bg-blue-50 text-blue-700'
                          : 'border-gray-300 hover:border-gray-400'
                      }`}
                    >
                      {type}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Your Problem</label>
                <textarea
                  value={problemText}
                  onChange={(e) => setProblemText(e.target.value)}
                  placeholder="Describe your problem in detail or paste the exact question..."
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 resize-none"
                  rows={4}
                />
              </div>

              <button className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-6 rounded-lg transition-colors flex items-center justify-center space-x-2">
                <Zap className="w-5 h-5" />
                <span>Get Step-by-Step Solution</span>
              </button>
            </div>
          </div>

          {/* Help Options */}
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-sm border p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Quick Help</h3>
              <div className="space-y-3">
                <button className="w-full p-3 text-left rounded-lg border hover:bg-gray-50 flex items-center space-x-3">
                  <MessageCircle className="w-5 h-5 text-blue-600" />
                  <div>
                    <div className="font-medium">Chat with AI Tutor</div>
                    <div className="text-sm text-gray-600">Real-time help and explanations</div>
                  </div>
                </button>
                <button 
                  onClick={() => setCurrentPage('generator')}
                  className="w-full p-3 text-left rounded-lg border hover:bg-gray-50 flex items-center space-x-3"
                >
                  <Video className="w-5 h-5 text-green-600" />
                  <div>
                    <div className="font-medium">Generate Tutorial Video</div>
                    <div className="text-sm text-gray-600">Create a custom video explanation</div>
                  </div>
                </button>
                <button className="w-full p-3 text-left rounded-lg border hover:bg-gray-50 flex items-center space-x-3">
                  <FileText className="w-5 h-5 text-purple-600" />
                  <div>
                    <div className="font-medium">Practice Problems</div>
                    <div className="text-sm text-gray-600">Similar problems to practice</div>
                  </div>
                </button>
              </div>
            </div>

            <div className="bg-blue-50 rounded-xl border border-blue-200 p-6">
              <h3 className="text-lg font-semibold text-blue-900 mb-3">Pro Tips</h3>
              <div className="space-y-2 text-sm text-blue-800">
                <div className="flex items-start space-x-2">
                  <Target className="w-4 h-4 mt-0.5 text-blue-600" />
                  <span>Be specific about what you're stuck on</span>
                </div>
                <div className="flex items-start space-x-2">
                  <Target className="w-4 h-4 mt-0.5 text-blue-600" />
                  <span>Include any work you've already done</span>
                </div>
                <div className="flex items-start space-x-2">
                  <Target className="w-4 h-4 mt-0.5 text-blue-600" />
                  <span>Ask for the reasoning, not just the answer</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const SearchResults = () => {
    const filteredVideos = sampleVideos.filter(video =>
      video.title.toLowerCase().includes(searchQuery.toLowerCase())
    );

    if (!searchQuery) return null;

    return (
      <div className="max-w-7xl mx-auto px-6 py-8">
        <BackButton />
        <h1 className="text-2xl font-bold text-gray-900 mb-6">
          Search results for "{searchQuery}"
        </h1>
       
        {filteredVideos.length > 0 ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredVideos.map(video => (
              <div key={video.id} className="bg-white rounded-xl shadow-sm border hover:shadow-lg transition-shadow cursor-pointer">
                <div className="aspect-video bg-gradient-to-br from-blue-100 to-purple-100 rounded-t-xl flex items-center justify-center text-4xl">
                  {video.thumbnail}
                </div>
                <div className="p-4">
                  <h3 className="font-semibold text-gray-900 mb-2">{video.title}</h3>
                  <div className="flex items-center justify-between text-sm text-gray-600">
                    <span>{video.duration}</span>
                    <span>{video.views} views</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <div className="text-gray-400 mb-4">
              <Search className="w-16 h-16 mx-auto" />
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No results found</h3>
            <p className="text-gray-600">Try a different search term or browse our courses</p>
          </div>
        )}
      </div>
    );
  };

  const renderCurrentPage = () => {
    if (searchQuery && currentPage === 'home') {
      return <SearchResults />;
    }

    switch (currentPage) {
      case 'home': return <HomePage />;
      case 'courses': return <CoursesPage />;
      case 'generator': return (
        <VideoGeneratorPage 
          formData={formData}
          setFormData={setFormData}
          error={error}
          setError={setError}
          isGenerating={isGenerating}
          setIsGenerating={setIsGenerating}
          progress={progress}
          setProgress={setProgress}
          currentStep={currentStep}
          setCurrentStep={setCurrentStep}
          generatedVideo={generatedVideo}
          setGeneratedVideo={setGeneratedVideo}
          backendConnected={backendConnected}
          setCurrentPage={setCurrentPage}
        />
      );
      case 'help': return <HelpPage />;
      default: return <HomePage />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      {renderCurrentPage()}
    </div>
  );
};

export default KhanAcademyApp;