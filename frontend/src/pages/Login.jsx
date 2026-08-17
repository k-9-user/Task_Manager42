import { useState } from 'react'
import "@fontsource/nabla";
import './login.css';
import { Link } from "react-router-dom";

function Login()
{
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");

	function handleSubmit(e) {
		e.preventDefault();
		console.log("Utilisateur : ${email}");
		console.log("Mot de passe : ${password}");
		// TODO: appel à authService.login(email, password)
	}
	return (
		<div className="login-page">
			<form className="login-box" onSubmit={handleSubmit}>
				<h1>Transcendance</h1>
				<input type="text" placeholder="Nom d'utilisateur" value={email} onChange={(e) => setUsername(e.target.value)}
				/>
				<input type="password" placeholder='Mot de passe' value={password} onChange={(e) => setPassword(e.target.value)}
				/>
				<button>Se connecter</button>
				<p><Link to="/Register">Creer un compte</Link></p>
			</form>
		</div>
	);
}

export default Login;