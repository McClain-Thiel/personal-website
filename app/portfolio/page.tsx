export default function Portfolio() {
  return (
    <section className="prose prose-neutral dark:prose-invert">
      <h1 className="mb-8">Portfolio</h1>
      
      <section className="mb-12">
        <h2>Professional Experience</h2>
        
        <div className="mb-8">
          <h3>Senior Machine Learning Engineer @ Snorkel AI</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">July 2024 - Present</p>
          <ul>
            <li>Leading research initiatives in clip-based compositional search evaluation</li>
            <li>Developing continuous training modules for applied machine learning team</li>
            <li>Optimizing LLM performance through distillation, quantization, and pruning</li>
          </ul>
        </div>

        <div className="mb-8">
          <h3>Senior Machine Learning Scientist @ Tempus</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">Sept 2023 - July 2024</p>
          <ul>
            <li>Founding member of the generative AI team</li>
            <li>Led development of LLM-powered applications scaling to hundreds of users</li>
            <li>Implemented secure and efficient alternatives to OpenAI's function calling</li>
          </ul>
        </div>

        <div className="mb-8">
          <h3>Previous Roles</h3>
          <ul>
            <li>AI Solution Architect @ Tempus (2022-2023)</li>
            <li>Data Scientist @ Nference (2021-2022)</li>
            <li>Data Scientist @ CureMetrix (2020-2021)</li>
          </ul>
        </div>
      </section>

      <section className="mb-12">
        <h2>Education</h2>
        <div className="mb-4">
          <h3>Georgia Institute of Technology</h3>
          <p>M.S. Computer Science (Expected 2025)</p>
        </div>
        <div>
          <h3>UC Berkeley</h3>
          <p>B.A. Data Science, Minor in Bioengineering (2020)</p>
        </div>
      </section>

      <section className="mb-12">
        <h2>Technical Skills</h2>
        <div className="flex flex-wrap gap-2">
          {[
            "Python", "PyTorch", "TensorFlow", "MLOps",
            "LLMs", "NLP", "Computer Vision",
            "Cloud Computing", "System Design",
            "Generative AI", "Distributed Computing"
          ].map((skill) => (
            <span key={skill} className="px-3 py-1 bg-gray-100 dark:bg-gray-800 rounded-full text-sm">
              {skill}
            </span>
          ))}
        </div>
      </section>
    </section>
  );
} 