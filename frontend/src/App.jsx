import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import AdminRoute from "./pages/AdminRoute";
import AdminUsers from "./pages/AdminUsers";
import Achievements from "./pages/Achievements";
import Login from "./pages/Login";
import OAuthCallback from "./pages/OAuthCallback";
import PrivacyPolicy from "./pages/PrivacyPolicy";
import PrivateRoute from "./pages/PrivateRoute";
import Profile from "./pages/Profile";
import ProjectDetail from "./pages/ProjectDetail";
import Projects from "./pages/Projects";
import Register from "./pages/Register";
import Search from "./pages/Search";
import Status from "./pages/Status";
import TermsOfService from "./pages/TermsOfService";
import Sidebar from "./components/Sidebar";
import Footer from "./components/Footer";
import "./App.css";

function AppContent() {
  const location = useLocation();
  const hideNavbar = location.pathname === "/login" || location.pathname === "/register" || location.pathname === "/oauth/callback";

  return (
    <div className="app-container">
      {!hideNavbar && <Sidebar />}
      <div className="app-body">
      <main className="app-content">
       <Routes>
         <Route path="/" element={<Navigate to="/login" />} />
         <Route path="/admin/users" element={<AdminRoute><AdminUsers /></AdminRoute>} />
         <Route path="/achievements" element={<PrivateRoute><Achievements /></PrivateRoute>} />
         <Route path="/login" element={<Login />} />
         <Route path="/oauth/callback" element={<OAuthCallback />} />
         <Route path="/PrivacyPolicy" element={<PrivacyPolicy />} />
         <Route path="/Profile" element={<Profile />} />
         <Route path="/projects/:id" element={<ProjectDetail />} />
         <Route path="/projects" element={<PrivateRoute><Projects /></PrivateRoute>} />
         <Route path="/register" element={<Register />} />
         <Route path="/Search" element={<Search />} />
         <Route path="/status" element={<Status />} />
         <Route path="/TermsOfService" element={<TermsOfService />} />
       </Routes>
      </main>
      <Footer />
      </div>
    </div>
  );
}

function App(){
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;
