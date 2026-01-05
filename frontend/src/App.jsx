import { useState, useEffect, useMemo, useRef, useLayoutEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts';
import {
  AlertTriangle, TrendingUp, MessageSquare, Eye, Heart, Repeat2,
  ExternalLink, Search, Info, X, ChevronDown, ChevronUp, Calendar
} from 'lucide-react';
import './App.css';

// In production (Docker), VITE_API_URL is empty and nginx proxies /api to backend
// In development, fallback to localhost:8000
const API_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');

// Color schemes
const SENTIMENT_COLORS = {
  'positive_hype': '#10b981',
  'neutral_informative': '#6b7280',
  'concerned_mundane': '#f59e0b',
  'concerned_xrisk': '#ef4444',
  'dismissive_skeptical': '#8b5cf6',
  'anti_ai_tribal': '#ec4899'
};

// Filter Modal component - almost full screen popup
function FilterModal({ isOpen, onClose, title, subtitle, posts, loading, onThesisClick, onTopicClick, onSentimentClick }) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <h2>{title}</h2>
            {subtitle && <p className="modal-subtitle">{subtitle}</p>}
          </div>
          <button className="modal-close" onClick={onClose}>
            <X size={24} />
          </button>
        </div>

        <div className="modal-content">
          {loading ? (
            <div className="modal-loading">
              <div className="loading-spinner"></div>
              <span>Loading posts...</span>
            </div>
          ) : posts && posts.length > 0 ? (
            <div className="posts-grid">
              {posts.map((post) => (
                <PostCard
                  key={post.uri}
                  post={post}
                  onThesisClick={onThesisClick}
                  onTopicClick={onTopicClick}
                  onSentimentClick={onSentimentClick}
                />
              ))}
            </div>
          ) : (
            <div className="modal-empty">
              <p>No posts found matching this filter.</p>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <span className="modal-count">
            {posts ? `${posts.length} posts` : ''}
          </span>
          <button className="modal-close-btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

// PostCard component with expandable text
function PostCard({ post, onThesisClick, onTopicClick, onSentimentClick }) {
  const [expanded, setExpanded] = useState(false);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const textRef = useRef(null);

  useLayoutEffect(() => {
    const el = textRef.current;
    if (el && !expanded) {
      setIsOverflowing(el.scrollHeight > el.clientHeight + 2);
    }
  }, [post.text, expanded]);

  return (
    <article className="post-card">
      <div className="post-header">
        <span className="post-author">{post.author}</span>
        <div className="post-badges">
          {post.similarity !== undefined && post.similarity < 1 && (
            <span className="similarity-badge">
              {(post.similarity * 100).toFixed(0)}% match
            </span>
          )}
          <span
            className="post-sentiment clickable"
            style={{ background: SENTIMENT_COLORS[post.sentiment] }}
            onClick={() => onSentimentClick && onSentimentClick(post.sentiment)}
          >
            {post.sentiment.replace(/_/g, ' ')}
          </span>
        </div>
      </div>
      <div
        ref={textRef}
        className={`post-text ${expanded ? 'expanded' : ''}`}
        onClick={() => isOverflowing && setExpanded(!expanded)}
        style={{ cursor: isOverflowing ? 'pointer' : 'default' }}
      >
        {post.text}
      </div>
      {(isOverflowing || expanded) && (
        <button className="expand-btn" onClick={() => setExpanded(!expanded)}>
          {expanded ? <><ChevronUp size={14} /> Show less</> : <><ChevronDown size={14} /> Show more</>}
        </button>
      )}
      {post.summary && (
        <p className="post-summary">
          <Info size={12} /> {post.summary}
        </p>
      )}
      <div className="post-meta">
        <div className="post-engagement">
          <span><Heart size={14} /> {post.likes || 0}</span>
          <span><Repeat2 size={14} /> {post.reposts || 0}</span>
          <span><MessageSquare size={14} /> {post.replies || 0}</span>
        </div>
        <a
          href={post.web_url}
          target="_blank"
          rel="noopener noreferrer"
          className="post-link"
        >
          View <ExternalLink size={12} />
        </a>
      </div>
      {post.theses && post.theses.length > 0 && (
        <div className="post-theses">
          {post.theses.map(t => (
            <span
              key={t}
              className={`thesis-tag ${post.thesis_stance || ''}`}
              onClick={() => onThesisClick && onThesisClick(t)}
            >
              {t}
            </span>
          ))}
        </div>
      )}
      {post.topics && post.topics.length > 0 && (
        <div className="post-topics">
          {post.topics.slice(0, 5).map(t => (
            <span
              key={t}
              className="topic-tag clickable"
              onClick={() => onTopicClick && onTopicClick(t)}
            >
              {t}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}

function App() {
  const [dashboardData, setDashboardData] = useState(null);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedThesis, setSelectedThesis] = useState(null);
  const [thesisDetail, setThesisDetail] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);

  // Date selection state (null = all dates, or { start: 'YYYY-MM-DD', end: 'YYYY-MM-DD' })
  const [selectedDateRange, setSelectedDateRange] = useState(null);
  const [availableDates, setAvailableDates] = useState([]);

  // Filter modal state
  const [filterModal, setFilterModal] = useState({ open: false, type: null, value: null, displayValue: null });
  const [filteredPosts, setFilteredPosts] = useState(null);
  const [filterLoading, setFilterLoading] = useState(false);

  useEffect(() => {
    fetchData(selectedDateRange);
  }, [selectedDateRange]);

  // Close modal on ESC key
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape' && filterModal.open) {
        closeFilterModal();
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [filterModal.open]);

  // Fetch filtered posts when modal filter changes
  useEffect(() => {
    const fetchFilteredPosts = async () => {
      if (!filterModal.open || !filterModal.type) {
        return;
      }

      const params = new URLSearchParams();
      if (filterModal.type === 'sentiment') params.set('sentiment', filterModal.value);
      if (filterModal.type === 'topic') params.set('topic', filterModal.value);
      if (filterModal.type === 'thesis') params.set('thesis', filterModal.value);
      // Include date range in filtered posts
      if (selectedDateRange?.start) params.set('start_date', selectedDateRange.start);
      if (selectedDateRange?.end) params.set('end_date', selectedDateRange.end);
      params.set('limit', '100');

      try {
        setFilterLoading(true);
        const res = await fetch(`${API_URL}/api/posts?${params}`);
        if (res.ok) {
          const data = await res.json();
          setFilteredPosts(data.posts);
        }
      } catch (err) {
        console.error('Failed to fetch filtered posts:', err);
      } finally {
        setFilterLoading(false);
      }
    };

    fetchFilteredPosts();
  }, [filterModal.open, filterModal.type, filterModal.value, selectedDateRange]);

  useEffect(() => {
    if (selectedThesis) {
      fetchThesisDetail(selectedThesis);
    }
  }, [selectedThesis]);

  const fetchData = async (dateRange = null) => {
    try {
      setLoading(true);

      // Build dashboard URL with date params
      let dashUrl = `${API_URL}/api/dashboard`;
      if (dateRange) {
        const params = new URLSearchParams();
        if (dateRange.start) params.set('start_date', dateRange.start);
        if (dateRange.end) params.set('end_date', dateRange.end);
        dashUrl += `?${params}`;
      }

      const [dashRes, configRes] = await Promise.all([
        fetch(dashUrl),
        fetch(`${API_URL}/api/config`)
      ]);

      if (!dashRes.ok || !configRes.ok) {
        throw new Error('Failed to fetch data');
      }

      const dashData = await dashRes.json();
      setDashboardData(dashData);
      setConfig(await configRes.json());

      // Store available dates (only on first load or when dates change)
      if (dashData.available_dates) {
        setAvailableDates(dashData.available_dates);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchThesisDetail = async (thesisId) => {
    try {
      const res = await fetch(`${API_URL}/api/thesis/${thesisId}`);
      if (res.ok) {
        setThesisDetail(await res.json());
      }
    } catch (err) {
      console.error('Failed to fetch thesis detail:', err);
    }
  };

  const performSemanticSearch = async (query) => {
    if (!query || query.length < 2) {
      setSearchResults(null);
      return;
    }
    try {
      setSearchLoading(true);
      const res = await fetch(`${API_URL}/api/search?q=${encodeURIComponent(query)}&limit=30`);
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data);
      }
    } catch (err) {
      console.error('Semantic search failed:', err);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleSearchKeyDown = (e) => {
    if (e.key === 'Enter' && searchTerm.length >= 2) {
      performSemanticSearch(searchTerm);
    }
  };

  const clearSearch = () => {
    setSearchTerm('');
    setSearchResults(null);
  };

  // Date selection handler
  const handleDateClick = (date) => {
    if (selectedDateRange?.start === date && selectedDateRange?.end === date) {
      // Clicking same date again clears selection (show all)
      setSelectedDateRange(null);
    } else {
      // Select single date
      setSelectedDateRange({ start: date, end: date });
    }
    // Clear search when changing dates
    clearSearch();
  };

  const clearDateFilter = () => {
    setSelectedDateRange(null);
    clearSearch();
  };

  // Format date for display (Jan 5)
  const formatDateShort = (dateStr) => {
    const date = new Date(dateStr + 'T00:00:00');
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  // Filter handlers - open modal with filter
  const handleSentimentClick = (sentimentId) => {
    const sentiment = dashboardData?.sentiment_distribution?.find(s => s.category === sentimentId);
    setFilteredPosts(null);
    setFilterModal({
      open: true,
      type: 'sentiment',
      value: sentimentId,
      displayValue: sentiment?.name || sentimentId.replace(/_/g, ' ')
    });
  };

  const handleTopicClick = (topicName) => {
    setFilteredPosts(null);
    setFilterModal({
      open: true,
      type: 'topic',
      value: topicName,
      displayValue: topicName
    });
  };

  const handleThesisClick = (thesisId) => {
    const thesis = config?.theses?.find(t => t.id === thesisId);
    setFilteredPosts(null);
    setFilterModal({
      open: true,
      type: 'thesis',
      value: thesisId,
      displayValue: thesis?.name || thesisId.replace(/_/g, ' ')
    });
    // Also fetch thesis detail for extra context
    setSelectedThesis(thesisId);
  };

  const closeFilterModal = () => {
    setFilterModal({ open: false, type: null, value: null, displayValue: null });
    setFilteredPosts(null);
    setSelectedThesis(null);
    setThesisDetail(null);
  };

  // Get modal title based on filter type
  const getModalTitle = () => {
    if (!filterModal.type) return '';
    const typeLabels = { sentiment: 'Sentiment', topic: 'Topic', thesis: 'MIRI Thesis' };
    return `${typeLabels[filterModal.type]}: ${filterModal.displayValue}`;
  };

  const getModalSubtitle = () => {
    if (filterModal.type === 'thesis' && thesisDetail) {
      return thesisDetail.thesis.short;
    }
    return null;
  };

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-content">
          <div className="loading-spinner"></div>
          <h2>Loading WatchEye Data...</h2>
          <p>Analyzing AI discourse sentiment</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-screen">
        <AlertTriangle size={48} />
        <h2>Connection Error</h2>
        <p>{error}</p>
        <button onClick={fetchData}>Retry</button>
      </div>
    );
  }

  const { 
    total_posts, 
    date_range, 
    sentiment_distribution, 
    thesis_tracking, 
    topic_distribution, 
    top_posts,
    xrisk_penetration 
  } = dashboardData;

  // Prepare chart data
  const sentimentChartData = sentiment_distribution.map(s => ({
    name: s.name.replace('/', '\n'),
    value: s.count,
    percentage: s.percentage.toFixed(1),
    id: s.category
  }));

  // Format thesis ID to readable label: "alignment_hard" -> "Alignment Hard"
  const formatThesisLabel = (id) => {
    return id.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  };

  const thesisChartData = thesis_tracking
    .filter(t => t.mention_count > 0)
    .map(t => ({
      name: formatThesisLabel(t.id),
      fullName: t.name,
      description: t.short,
      mentions: t.mention_count,
      percentage: t.mention_percentage,
      supports: t.support_count,
      counters: t.counter_count,
      id: t.id
    }));

  // Calculate total % of posts engaging with ANY MIRI thesis
  const anyThesisPct = thesis_tracking.length > 0
    ? (thesis_tracking.reduce((sum, t) => {
        // Count unique posts with any thesis (can't sum percentages directly)
        return sum + t.mention_count;
      }, 0) / total_posts * 100).toFixed(1)
    : 0;

  const topicChartData = topic_distribution.slice(0, 20).map(t => ({
    name: t.topic,
    count: t.count,
    percentage: t.percentage.toFixed(1)
  }));

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <Eye className="logo-icon" />
            <div>
              <h1>MIRI WatchEye</h1>
              <p className="subtitle">AI Discourse Sentiment & Thesis Tracking</p>
            </div>
          </div>
          <div className="header-stats">
            <div className="stat">
              <span className="stat-value">{total_posts.toLocaleString()}</span>
              <span className="stat-label">Posts Analyzed</span>
            </div>
            <div className="stat highlight">
              <span className="stat-value">{xrisk_penetration.toFixed(1)}%</span>
              <span className="stat-label">X-Risk Penetration</span>
            </div>
            <div className="stat">
              <span className="stat-value">
                {selectedDateRange
                  ? formatDateShort(selectedDateRange.start)
                  : availableDates.length > 0
                    ? `${formatDateShort(availableDates[0].date)} - ${formatDateShort(availableDates[availableDates.length - 1].date)}`
                    : 'N/A'}
              </span>
              <span className="stat-label">{selectedDateRange ? 'Selected Date' : 'Date Range'}</span>
            </div>
          </div>
        </div>
      </header>

      <main className="main-content">
        {/* Date picker */}
        <div className="date-picker">
          <div className="date-picker-label">
            <Calendar size={16} />
            <span>Date:</span>
          </div>
          <div className="date-buttons">
            <button
              className={`date-btn ${!selectedDateRange ? 'active' : ''}`}
              onClick={clearDateFilter}
            >
              All
            </button>
            {availableDates.map((d) => (
              <button
                key={d.date}
                className={`date-btn ${selectedDateRange?.start === d.date ? 'active' : ''}`}
                onClick={() => handleDateClick(d.date)}
              >
                <span className="date-label">{formatDateShort(d.date)}</span>
                <span className="date-count">{d.count}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Instruction hint */}
        <div className="chart-hint">
          <MessageSquare size={16} />
          <span>Click on any chart segment or bar to explore posts in that category</span>
        </div>

        {/* Top Row: Sentiment + Thesis */}
        <section className="metrics-row top-row">
          <div className="metric-card sentiment-overview">
            <h3><TrendingUp size={18} /> Sentiment Distribution</h3>
            <div className="chart-container">
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={sentimentChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={2}
                    dataKey="value"
                    onClick={(data) => handleSentimentClick(data.id)}
                  >
                    {sentimentChartData.map((entry) => (
                      <Cell
                        key={entry.id}
                        fill={SENTIMENT_COLORS[entry.id] || '#666'}
                        stroke="transparent"
                        strokeWidth={2}
                        style={{ cursor: 'pointer' }}
                      />
                    ))}
                  </Pie>
                  <Tooltip 
                    formatter={(value, name, props) => [
                      `${value} posts (${props.payload.percentage}%)`,
                      props.payload.name
                    ]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="legend">
              {sentimentChartData.map((s) => (
                <div
                  key={s.id}
                  className="legend-item"
                  onClick={() => handleSentimentClick(s.id)}
                >
                  <span
                    className="legend-color"
                    style={{ background: SENTIMENT_COLORS[s.id] }}
                  />
                  <span className="legend-label">{s.name}</span>
                  <span className="legend-value">{s.percentage}%</span>
                </div>
              ))}
            </div>
          </div>

          <div className="metric-card thesis-overview">
            <h3><AlertTriangle size={18} /> MIRI Thesis Tracking</h3>
            <p className="card-description">
              How often do AI safety arguments appear in public discourse?
              <span className="thesis-overall-stat">
                {anyThesisPct}% of posts mention MIRI-related themes
              </span>
            </p>
            <div className="chart-container">
              <ResponsiveContainer width="100%" height={320}>
                <BarChart
                  data={thesisChartData}
                  layout="vertical"
                  margin={{ left: 10, right: 30 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis
                    type="number"
                    stroke="#888"
                    tickFormatter={(v) => `${v}%`}
                    domain={[0, 'auto']}
                  />
                  <YAxis
                    dataKey="name"
                    type="category"
                    width={160}
                    tick={{ fill: '#ccc', fontSize: 13 }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: '#1a1a2e',
                      border: '1px solid #333',
                      borderRadius: '8px',
                      maxWidth: '300px'
                    }}
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0].payload;
                      return (
                        <div style={{ padding: '8px 12px', background: '#1a1a2e', border: '1px solid #333', borderRadius: '8px' }}>
                          <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>{d.fullName}</div>
                          <div style={{ fontSize: '12px', color: '#aaa', marginBottom: '6px' }}>{d.description}</div>
                          <div style={{ color: '#3b82f6', fontWeight: 'bold' }}>{d.percentage}% of posts</div>
                          <div style={{ color: '#888', fontSize: '12px' }}>({d.mentions} mentions)</div>
                        </div>
                      );
                    }}
                  />
                  <Bar
                    dataKey="percentage"
                    fill="#3b82f6"
                    radius={[0, 4, 4, 0]}
                    onClick={(data) => handleThesisClick(data.id)}
                    style={{ cursor: 'pointer' }}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>

        {/* Topic Distribution - Full Width */}
        <section className="topic-row">
          <div className="metric-card topic-overview">
            <h3><MessageSquare size={18} /> Topic Distribution (Top 20)</h3>
            <div className="chart-container">
              <ResponsiveContainer width="100%" height={580}>
                <BarChart
                  data={topicChartData}
                  layout="vertical"
                  margin={{ left: 20, right: 40 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis type="number" stroke="#888" />
                  <YAxis
                    dataKey="name"
                    type="category"
                    width={220}
                    tick={{ fill: '#ccc', fontSize: 13 }}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0].payload;
                      return (
                        <div style={{ padding: '8px 12px', background: '#1a1a2e', border: '1px solid #333', borderRadius: '8px' }}>
                          <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>{d.name}</div>
                          <div style={{ color: '#8b5cf6' }}>{d.count} posts ({d.percentage}%)</div>
                        </div>
                      );
                    }}
                  />
                  <Bar
                    dataKey="count"
                    fill="#8b5cf6"
                    radius={[0, 4, 4, 0]}
                    onClick={(data) => handleTopicClick(data.name)}
                    style={{ cursor: 'pointer' }}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>

        {/* Posts Feed */}
        <section className="posts-section">
          <div className="posts-header">
            <h3>
              <MessageSquare size={18} />
              {searchResults
                ? `Search Results (${searchResults.total})`
                : 'Top Engaged Posts'}
            </h3>
            <div className="posts-filters">
              <div className="search-box">
                <Search size={16} />
                <input
                  type="text"
                  placeholder="Semantic search... (Enter to search)"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  onKeyDown={handleSearchKeyDown}
                />
                {searchResults && (
                  <button className="clear-search" onClick={clearSearch}>×</button>
                )}
              </div>
              {searchLoading && <span className="search-loading">Searching...</span>}
              {searchResults && (
                <span className="search-type-badge">
                  {searchResults.search_type === 'semantic' ? '🔮 Semantic' : '📝 Text'}
                </span>
              )}
            </div>
          </div>

          <div className="posts-grid">
            {(searchResults ? searchResults.results : top_posts)
              .slice(0, 30)
              .map((post) => (
                <PostCard
                  key={post.uri}
                  post={post}
                  onThesisClick={handleThesisClick}
                  onTopicClick={handleTopicClick}
                  onSentimentClick={handleSentimentClick}
                />
              ))}
          </div>
        </section>
      </main>

      {/* Filter Modal */}
      <FilterModal
        isOpen={filterModal.open}
        onClose={closeFilterModal}
        title={getModalTitle()}
        subtitle={getModalSubtitle()}
        posts={filteredPosts}
        loading={filterLoading}
        onThesisClick={handleThesisClick}
        onTopicClick={handleTopicClick}
        onSentimentClick={handleSentimentClick}
      />

      <footer className="footer">
        <p>
          MIRI WatchEye • AI Discourse Analysis Tool •
          Built for Machine Intelligence Research Institute
        </p>
      </footer>
    </div>
  );
}

export default App;
