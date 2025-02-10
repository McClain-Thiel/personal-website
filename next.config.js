/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  basePath: process.env.NEXT_PUBLIC_BASE_PATH,
  images: {
    unoptimized: true,
  },
  // Exclude the /og route from static export
  distDir: 'out',
  exportPathMap: async function () {
    return {
      '/': { page: '/' },
      // Add other static routes here
      // '/blog': { page: '/blog' },
      // '/portfolio': { page: '/portfolio' },
      // '/projects': { page: '/projects' },
    }
  }
}

module.exports = nextConfig 