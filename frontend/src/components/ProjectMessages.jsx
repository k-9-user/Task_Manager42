import { useEffect, useState } from "react";
import { getProjectMessages, sendProjectMessage, deleteProjectMessage } from "../services/projectService";
import { useTranslation } from "react-i18next";
import "./ProjectMessages.css";

function ProjectMessages({ projectId, currentUserId, isOwner })
{
	const [messages, setMessages] = useState([]);
	const [content, setContent] = useState("");
	const [loading, setLoading] = useState(true);
	const [posting, setPosting] = useState(false);
	const [error, setError] = useState("");
	const { t } = useTranslation();

	useEffect(() =>
	{
		async function fetchMessages()
		{
			try
			{
				const data = await getProjectMessages(projectId);
				setMessages(data.messages);
			}
			catch (err)
			{
				setError(err.message);
			}
			finally
			{
				setLoading(false);
			}
		}
		fetchMessages();
	}, [projectId]);

	async function handleSubmit(e)
	{
		e.preventDefault();
		if (!content.trim())
			return ;

		setPosting(true);
		setError("");
		try
		{
			const data = await sendProjectMessage(projectId, content.trim());
			setMessages([...messages, data.message]);
			setContent("");
		}
		catch (err)
		{
			setError(err.message);
		}
		finally
		{
			setPosting(false);
		}
	}

	async function handleDelete(messageId)
	{
		try
		{
			await deleteProjectMessage(messageId);
			setMessages(messages.filter((m) => m.id !== messageId));
		}
		catch (err)
		{
			setError(err.message);
		}
	}

	return (
		<div className="project-messages">
			<h3>{t("messages.title")}</h3>
			{loading ? (
				<p>{t("loading.load")}</p>
			) : (
				<ul className="message-list">
					{messages.map((message) => (
						<li key={message.id} className="message-item">
							<div className="message-meta">
								<span className="message-author">{message.author_username}</span>
								{(message.author_id === currentUserId || isOwner) && (
									<button className="message-delete" onClick={() => handleDelete(message.id)}>✕</button>
								)}
							</div>
							<p className="message-content">{message.content}</p>
						</li>
					))}
					{messages.length === 0 && <li className="message-empty">{t("messages.empty")}</li>}
				</ul>
			)}
			<form onSubmit={handleSubmit} className="message-form">
				<textarea
					value={content}
					onChange={(e) => setContent(e.target.value)}
					placeholder={t("messages.placeholder")}
				/>
				<button type="submit" disabled={posting}>
					{posting ? t("random.envoi") : t("messages.send")}
				</button>
			</form>
			{error && <p className="error">{error}</p>}
		</div>
	);
}

export default ProjectMessages;
