import { useNavigate } from 'react-router-dom';

const INTERVIEW_TYPES = [
    {
        id: 'hr',
        icon: '👔',
        title: 'HR Interview',
        description: 'Behavioral and situational questions. Practice answering about your experience, strengths, weaknesses, and career goals.',
        questions: '10 questions',
        difficulty: 'Mixed',
    },
    {
        id: 'viva',
        icon: '💻',
        title: 'Viva',
        description: 'Programming, system design, and CS fundamentals. Test your technical knowledge and problem-solving skills via verbal answers.',
        questions: '10 questions',
        difficulty: 'Medium-Hard',
    },
    {
        id: 'dsa',
        icon: '🧩',
        title: 'Technical (DSA)',
        description: 'Solve DSA problems by writing your approach & pseudocode. Scored by AI on correctness, complexity, and clarity.',
        questions: '3 questions',
        difficulty: 'Medium-Hard',
        isDSA: true,
    },
    {
        id: 'exam',
        icon: '📝',
        title: 'Exam / Viva',
        description: 'Academic and conceptual questions covering data structures, algorithms, OS, DBMS and more.',
        questions: '10 questions',
        difficulty: 'Mixed',
    },
];

export default function InterviewSelectPage() {
    const navigate = useNavigate();

    const handleSelect = (type) => {
        if (type === 'dsa') {
            navigate('/dsa');
        } else {
            navigate(`/interview/${type}`);
        }
    };

    return (
        <div className="page">
            <div className="page-header">
                <h1 className="page-title">Choose Interview Type</h1>
                <p className="page-subtitle">Select the type of mock interview you want to practice</p>
            </div>

            <div className="type-cards">
                {INTERVIEW_TYPES.map((type) => (
                    <div
                        key={type.id}
                        className="card type-card"
                        onClick={() => handleSelect(type.id)}
                    >
                        <div className="type-icon">{type.icon}</div>
                        <div className="type-title">{type.title}</div>
                        <div className="type-desc">{type.description}</div>
                        <div className="type-meta">
                            <span>{type.questions}</span>
                            <span>•</span>
                            <span>{type.difficulty}</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
