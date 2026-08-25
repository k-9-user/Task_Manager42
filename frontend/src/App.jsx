import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import Login from "./pages/Login";
import Profile from "./pages/Profile";
import ProjectDetail from "./pages/ProjectDetail";
import Projects from "./pages/Projects";
import Register from "./pages/Register";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import { useAuth } from "./hooks/useAuth";
import "./App.css";

//:id url dynamique, toute valeurs ajoute apres /projects/ sera prise en compte dans le composant

function PrivateRoute({ children }) {
  const { isAuthen, loading } = useAuth();
  if (loading) return null;
  return isAuthen ? children : <Navigate to="/login" />;
}

function AppContent() {
  const location = useLocation();
  const hideNavbar = location.pathname === "/login" || location.pathname === "/register";

  return (
    <>
      {!hideNavbar && <Navbar />}
      <Routes>
        <Route path="/" element={<Navigate to="/login" />} />
        <Route path="/login" element={<Login />} />
        <Route path="/Profile" element={<PrivateRoute><Profile /></PrivateRoute>} />
        <Route path="/projects/:id" element={<PrivateRoute><ProjectDetail /></PrivateRoute>} />
        <Route path="/projects" element={<PrivateRoute><Projects /></PrivateRoute>} />
        <Route path="/register" element={<Register />} />
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