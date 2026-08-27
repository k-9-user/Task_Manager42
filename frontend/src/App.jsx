import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import AdminUsers from "./pages/AdminUsers";
import Login from "./pages/Login";
import PrivacyPolicy from "./pages/PrivacyPolicy";
import PrivateRoute from "./pages/PrivateRoute";
import Profile from "./pages/Profile";
import ProjectDetail from "./pages/ProjectDetail";
import Projects from "./pages/Projects";
import Register from "./pages/Register";
import Search from "./pages/Search";
import TermsOfService from "./pages/TermsOfService";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import "./App.css";

//:id url dynamique, toute valeurs ajoute apres /projects/ sera prise en compte dans le composant

function AppContent() {
  const location = useLocation();
  const hideNavbar = location.pathname === "/login" || location.pathname === "/register";

  return (
    <>
      {!hideNavbar && <Navbar />}
      <Routes>
        <Route path="/" element={<Navigate to="/login" />} />
        <Route path="/admin/users" element={<AdminUsers />} />
        <Route path="/login" element={<Login />} />
        <Route path="/PrivacyPolicy" element={<PrivacyPolicy />} />
        <Route path="/Profile" element={<Profile />} />
        <Route path="/projects/:id" element={<ProjectDetail />} />
        <Route path="/projects" element={<PrivateRoute><Projects /></PrivateRoute>} />
        <Route path="/register" element={<Register />} />
        <Route path="/Search" element={<Search />} />
        <Route path="/TermsOfService" element={<TermsOfService />} />
      </Routes>
      <Footer />
    </>
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