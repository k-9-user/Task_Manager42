import { useState } from 'react'
import { useNavigate, Link } from "react-router-dom";
import { login as loginApi } from "../services/authService";
import { useAuth } from "../hooks/useAuth";
import "@fontsource/nabla";
import './login.css';

function Login()
{
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [error, setError] = useState("");
	const { login } = useAuth();
	const navigate = useNavigate();

	async function handleSubmit(e) {
		e.preventDefault();
		setError("");
		try {
			const data = await loginApi(email, password);
			login(data.token);
			navigate("/projects");
		} catch (err) {
			setError(err.message);
		}
	}
	return (
		<div className="login-page">
			<form className="login-box" onSubmit={handleSubmit}>
				<h1>Transcendance</h1>
				{error && <p className="error">{error}</p>}
				<input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)}
				/>
				<input type="password" placeholder='Mot de passe' value={password} onChange={(e) => setPassword(e.target.value)}
				/>
				<button>Se connecter</button>
				<p><Link to="/register">Creer un compte</Link></p>
			</form>
		</div>
	);
}

export default Login;
