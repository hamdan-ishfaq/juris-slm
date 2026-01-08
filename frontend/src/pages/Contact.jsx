import { Mail, Github, Globe } from 'lucide-react';

export default function Contact() {
  return (
    <div className="min-h-screen bg-gray-950 pt-20 px-4 flex items-center justify-center">
      <div className="max-w-lg w-full bg-gray-900 rounded-2xl p-8 border border-gray-800">
        <h2 className="text-3xl font-bold text-white mb-6">Contact Developer</h2>
        <div className="space-y-6">
          <div className="flex items-center gap-4 text-gray-300">
            <div className="p-3 bg-gray-800 rounded-lg"><Mail className="w-6 h-6 text-blue-400" /></div>
            <div>
              <p className="text-sm text-gray-500">Email</p>
              <p className="font-medium">hamdan.ishfaq@nust.edu.pk</p>
            </div>
          </div>
          <div className="flex items-center gap-4 text-gray-300">
            <div className="p-3 bg-gray-800 rounded-lg"><Github className="w-6 h-6 text-purple-400" /></div>
            <div>
              <p className="text-sm text-gray-500">GitHub</p>
              <p className="font-medium">github.com/hamdanishfaq</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}