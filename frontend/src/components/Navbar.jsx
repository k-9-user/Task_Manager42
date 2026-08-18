import { Link } from "react-router-dom";
import './Navbar.css';

function Navbar()
{
	return (
		<nav className="navbar">
			<div className="navbar-logo">Task Manager</div>
			<div className="navbar-links">
				<Link to="/projects">Projets </Link>
				<Link to="/login"> Se connecter</Link>
			</div>
		</nav>
	);
}

export default Navbar;