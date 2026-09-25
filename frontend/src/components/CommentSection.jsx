import { useEffect, useState } from "react";
import { getTaskComments, addComment, deleteComment } from "../services/taskService";
import { useTranslation } from "react-i18next";

function CommentSection({ taskId, currentUserId, isOwner })
{
	const [comments, setComments] = useState([]);
	const [content, setContent] = useState("");
	const [loading, setLoading] = useState(true);
	const [posting, setPosting] = useState(false);
	const [error, setError] = useState("");
	const { t } = useTranslation();

	useEffect(() =>
	{
		async function fetchComments()
		{
			try
			{
				const data = await getTaskComments(taskId);
				setComments(data.comments);
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
		fetchComments();
	}, [taskId]);

	async function handleSubmit(e)
	{
		e.preventDefault();
		if (!content.trim())
		{
			setError(t("error.required"));
			return ;
		}

		setPosting(true);
		setError("");
		try
		{
			const data = await addComment(taskId, content.trim());
			setComments([...comments, data.comment]);
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

	async function handleDelete(commentId)
	{
		try
		{
			await deleteComment(commentId);
			setComments(comments.filter((c) => c.id !== commentId));
		}
		catch (err)
		{
			setError(err.message);
		}
	}

	return (
		<div>
			{loading ? (
				<p>{t("loading.load")}</p>
			) : (
				<ul>
					{comments.map((comment) => (
						<li key={comment.id}>
							<p>{comment.content}</p>
							{(comment.author_id === currentUserId || isOwner) && (
								<button onClick={() => handleDelete(comment.id)}>{t("comments.delete")}</button>
							)}
						</li>
					))}
				</ul>
			)}
			<form onSubmit={handleSubmit}>
				<textarea
					value={content}
					onChange={(e) => setContent(e.target.value)}
					placeholder={t("comments.placeholder")}
					aria-label={t("comments.placeholder")}
					maxLength={5000}
				/>
				<button type="submit" disabled={posting}>
					{posting ? t("loading.sending") : t("comments.submit")}
				</button>
			</form>
			{error && <p className="error">{error}</p>}
		</div>
	);
}

export default CommentSection;
