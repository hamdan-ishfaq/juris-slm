import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Chat from './pages/Chat';
import Upload from './pages/Upload';
import Contact from './pages/Contact';
import Evaluation from './pages/Evaluation';
import Diagnostics from './pages/Diagnostics';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-950 text-white font-sans">
        <Navbar />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/eval" element={<Evaluation />} />
          <Route path="/diagnostics" element={<Diagnostics />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;