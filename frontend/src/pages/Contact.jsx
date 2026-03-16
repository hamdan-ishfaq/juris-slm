import { motion } from 'framer-motion';
import { Mail, Phone, MapPin } from 'lucide-react';

export default function Contact() {
  return (
    <div className="min-h-screen bg-gray-950 pt-24 pb-12 px-4">
      <div className="max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="text-4xl font-bold text-white mb-4">Contact Us</h1>
          <p className="text-gray-400 mb-12">
            Have questions about BEWEIS? Get in touch with our team.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                icon: <Mail className="w-8 h-8" />,
                title: "Email",
                value: "support@beweis-legal.com"
              },
              {
                icon: <Phone className="w-8 h-8" />,
                title: "Phone",
                value: "+1 (555) 123-4567"
              },
              {
                icon: <MapPin className="w-8 h-8" />,
                title: "Address",
                value: "Berlin, Germany"
              }
            ].map((item, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.1 }}
                className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-center"
              >
                <div className="text-blue-400 mb-4 flex justify-center">{item.icon}</div>
                <h3 className="text-xl font-semibold text-white mb-2">{item.title}</h3>
                <p className="text-gray-400">{item.value}</p>
              </motion.div>
            ))}
          </div>

          <motion.form
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="mt-12 bg-gray-900 border border-gray-800 rounded-xl p-8"
          >
            <h2 className="text-2xl font-bold text-white mb-6">Send us a Message</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-gray-300 font-semibold mb-2">Name</label>
                <input
                  type="text"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-blue-500 focus:outline-none"
                  placeholder="Your name"
                />
              </div>
              <div>
                <label className="block text-gray-300 font-semibold mb-2">Email</label>
                <input
                  type="email"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-blue-500 focus:outline-none"
                  placeholder="your@email.com"
                />
              </div>
              <div>
                <label className="block text-gray-300 font-semibold mb-2">Message</label>
                <textarea
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-blue-500 focus:outline-none h-32"
                  placeholder="Your message..."
                />
              </div>
              <button
                type="submit"
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 rounded-lg transition-all"
              >
                Send Message
              </button>
            </div>
          </motion.form>
        </motion.div>
      </div>
    </div>
  );
}