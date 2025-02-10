import Image from "next/image";
import { socialLinks } from "./config";

export default function Page() {
  return (
    <section>
        <Image
          src="/profile.jpg"
          alt="Profile photo"
          className="rounded-full bg-gray-100 block lg:mt-5 mt-0 lg:mb-5 mb-10 mx-auto sm:float-right sm:ml-5 sm:mb-5 grayscale hover:grayscale-0"
          unoptimized
          width={160}
          height={160}
          priority
        />
      <h1 className="mb-8 text-2xl font-medium tracking-tight">
        Hi, I'm McClain
      </h1>
      <div className="prose prose-neutral dark:prose-invert">
        <p>
          I'm a Senior Machine Learning Engineer at <a href="https://snorkel.ai">Snorkel AI</a>, specializing in 
          machine learning and AI systems. With a background spanning genomics and clinical informatics, 
          I focus on developing AI-driven solutions that enhance operational efficiency and insights.
        </p>
        <p>
          Previously, I've worked at Tempus and Nference, where I led initiatives in generative AI, 
          clinical algorithms, and MLOps. I studied Data Science and Bioengineering at UC Berkeley 
          and am currently pursuing advanced Computer Science studies at Georgia Tech.
        </p>
        <p>
          Outside of work, I play basketball, padel and travel a lot. Find me on <a href="">Playtomic</a>.
        </p>
        <p>
          Feel free to explore my <a href="/portfolio">portfolio</a> to learn more about my professional 
          experience, or check out my <a href="/blog">blog</a> where I write about biology and sequence models.
        </p>
      </div>
    </section>
  );
}
