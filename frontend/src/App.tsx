import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import BloggerHeatmap from './pages/BloggerHeatmap'
import TodaySignals from './pages/TodaySignals'
import BloggerManage from './pages/BloggerManage'
import PortfolioPage from './pages/PortfolioPage'
import LearnPage from './pages/LearnPage'
import ReviewPage from './pages/ReviewPage'
import SignalReviewPage from './pages/SignalReviewPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/heatmap" replace />} />
        <Route path="heatmap" element={<BloggerHeatmap />} />
        <Route path="signal" element={<TodaySignals />} />
        <Route path="bloggers" element={<BloggerManage />} />
        <Route path="portfolio" element={<PortfolioPage />} />
        <Route path="learn" element={<LearnPage />} />
        <Route path="review" element={<ReviewPage />} />
        <Route path="signal-reviews" element={<SignalReviewPage />} />
      </Route>
    </Routes>
  )
}
