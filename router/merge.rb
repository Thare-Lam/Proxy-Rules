require 'yaml'

runtime, overlay_path = ARGV
config = YAML.safe_load(File.read(runtime), aliases: true)
overlay = YAML.safe_load(File.read(overlay_path))
keys = ['proxy-groups', 'rule-providers', 'rules']
abort 'Unexpected overlay fields' unless overlay.is_a?(Hash) && overlay.keys.sort == keys.sort
abort 'Invalid groups' unless overlay['proxy-groups'].is_a?(Array) && !overlay['proxy-groups'].empty?
abort 'Invalid rules' unless overlay['rules'].is_a?(Array) && overlay['rules'].last.start_with?('MATCH,')
abort 'Invalid providers' unless overlay['rule-providers'].is_a?(Hash)
keys.each { |key| config[key] = overlay[key] }
temporary = "#{runtime}.unified.#{Process.pid}"
begin
  File.open(temporary, File::WRONLY | File::CREAT | File::EXCL, 0600) do |file|
    file.write(YAML.dump(config))
    file.flush
    file.fsync
  end
  File.rename(temporary, runtime)
ensure
  File.unlink(temporary) if File.exist?(temporary)
end
