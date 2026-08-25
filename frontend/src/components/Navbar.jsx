import { Link } from "react-router-dom";
import './Navbar.css';
import { useAuth } from "../hooks/useAuth";

function Navbar()
{
	const { isAuthen, logout } = useAuth();
	return (
		<nav className="navbar">
			<div className="navbar-logo">Task Manager</div>
			<div className="navbar-links">
				<Link to="/projects">Projets </Link>
				{ isAuthen ?
					(
						<button onClick={logout}> Se deconnecter</button>
					)
					:
					(
						<Link to="/login"> Se connecter</Link>
					)
				}
			</div>
		</nav>
	);
}

export default Navbar;